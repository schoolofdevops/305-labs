# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""OpsMate synthetic training data — turn the runbook corpus into Q&A pairs.

The idea in one line: you already have the textbook (the corpus). Before an exam
you do not re-read the textbook, you build a PRACTICE QUESTION BANK from it and
drill that. This script does exactly that for the model — it walks each runbook
section and asks a local model (Ollama qwen3:0.6b, think:false) for a few
grounded question/answer pairs about THAT section, then quality-filters the
result and splits it into train/eval JSONL in the same chat shape the app uses.

Why per-section: the app chunks each runbook on its `## headings` (see
app/main.py `chunk_markdown`). Generating one small batch of Q&A per section
keeps every pair anchored to a real passage — the same discipline the golden set
uses (`source:` on every question). A pair we cannot trace back to a section, we
throw away.

CONTAMINATION RULE (read this): the M5 golden set is HELD OUT. It is the yardstick
M6 must beat, so it must never appear in training data — training on your test set
is cheating and inflates every number that follows. This script only ever reads
the CORPUS (labs/opsmate/corpus/*.md); it never reads golden.yaml. The questions
it invents will resemble golden questions in TOPIC (same runbooks) but are freshly
generated and quality-filtered — and we still measure against the untouched golden
set at the end. Same sources, different questions, held-out test: that is the line.

Usage:
  uv run labs/m6/synthesize.py                 # full corpus -> ~150-300 pairs
  uv run labs/m6/synthesize.py --max-sections 2  # smoke test: first 2 sections
  uv run labs/m6/synthesize.py --per-section 3 --out-dir labs/opsmate/train

Env / flags:
  OLLAMA_URL       host Ollama base URL        (default http://localhost:11434)
  --model          generator model             (default qwen3:0.6b)
  --corpus         corpus dir                  (default labs/opsmate/corpus)
  --per-section    Q&A pairs to ask per section (default 3)
  --max-sections   cap sections (smoke tests)  (default 0 = all)
  --eval-frac      fraction held for eval split (default 0.1)
  --out-dir        where train.jsonl/eval.jsonl land (default labs/opsmate/train)
  --seed           shuffle seed for the split  (default 13)

Output:
  <out-dir>/train.jsonl   chat-format samples for train_lora.py
  <out-dir>/eval.jsonl    a small held-out slice (loss sanity, NOT the golden set)
  <out-dir>/rejects.jsonl  filtered-out candidates + the reason (inspect these!)
"""
import os
import re
import csv  # noqa: F401 — kept for readers who extend the reject log to CSV
import sys
import json
import glob
import random
import argparse
import datetime

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# The app's system-prompt FAMILY. Training samples must carry the same system
# role the server applies at inference, or the model learns to answer a prompt it
# will never see (the chat-template pitfall — see the M6 deep dive). This is the
# short v1 prompt from prompts/system.txt, trimmed of the CONTEXT-injection lines
# that only apply when retrieval is in front of the model. The tuned model is
# taught OpsMate's voice and format directly, so at serve time it answers well
# whether or not RAG is attached.
SYSTEM_PROMPT = (
    "You are OpsMate, an SRE assistant for on-call engineers during incidents. "
    "Answer with the concrete diagnostic or remediation step — the command, the "
    "metric to check, or the decision — grounded in the team's runbooks. If you "
    "do not have a runbook for something, say so plainly rather than inventing steps."
)

# The generator prompt. It gets ONE runbook section and must return a small JSON
# array of {question, answer} objects grounded in that section. think:false and a
# tight instruction keep the 0.6B model on-format (proven in the M6 spike).
GEN_INSTRUCTION = """You are building a training dataset for an SRE assistant.

Below is one section of an internal runbook (source file: {source}).

Write exactly {n} distinct question/answer pairs that an on-call engineer might
ask, where the ANSWER is fully contained in this section. Rules:
- The question must sound like a real engineer during an incident, not a quiz.
- The answer must be a concrete step, command, metric, or decision FROM the text.
- Do NOT invent facts, numbers, or commands that are not in the section.
- Keep each answer to 1-3 sentences.
- Mention the source file "{source}" in the answer where it is natural.

Return ONLY a JSON array, no prose, in exactly this shape:
[{{"question": "...", "answer": "..."}}, ...]

RUNBOOK SECTION:
<<<
{section}
>>>"""


def split_sections(text: str, source: str) -> list[dict]:
    """Split a runbook on its ## headings — the same boundary the app chunks on,
    so every training pair is anchored to a passage retrieval would also return.
    A very short lead-in before the first heading is ignored (title only)."""
    parts = re.split(r"(?m)^(?=##\s)", text)
    sections = []
    for part in parts:
        body = part.strip()
        if not body or not body.startswith("##"):
            continue
        heading = re.match(r"##\s*(.+)", body)
        # A section needs some substance to generate a grounded pair from.
        if len(body.split()) < 12:
            continue
        sections.append({
            "source": source,
            "heading": heading.group(1).strip() if heading else source,
            "text": body,
        })
    return sections


def generate(model: str, section: dict, n: int) -> list[dict]:
    """Ask the local model for n grounded Q&A pairs about one section. Returns a
    (possibly empty) list of raw {question, answer} dicts — filtering happens later."""
    prompt = GEN_INSTRUCTION.format(source=section["source"], n=n, section=section["text"])
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.4},
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    raw = resp.json().get("response", "")
    return parse_pairs(raw)


def parse_pairs(raw: str) -> list[dict]:
    """Pull the JSON array out of the model's reply. Small models wrap it in code
    fences or stray prose; grab the first [...] block and parse that. A parse
    failure returns [] (the whole section is then counted as a reject)."""
    raw = raw.strip()
    # Strip a leading <think> block if the model emitted one despite think:false.
    raw = re.sub(r"(?s)^<think>.*?</think>", "", raw).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    pairs = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and "question" in item and "answer" in item:
            pairs.append({"question": str(item["question"]).strip(),
                          "answer": str(item["answer"]).strip()})
    return pairs


# --- the quality filter — garbage in, garbage out --------------------------
# A synthetic set is only as good as what survives filtering. Each rule below
# throws out a specific failure mode the 0.6B generator produces, and every
# reject is logged with its reason so you can SEE the garbage you kept out.
MIN_Q, MAX_Q = 12, 400        # question length in chars
MIN_A, MAX_A = 15, 700        # answer length in chars


def filter_pairs(pairs: list[dict], section: dict, seen: set) -> tuple[list[dict], list[dict]]:
    kept, rejected = [], []
    for p in pairs:
        q, a = p["question"], p["answer"]
        reason = None
        if not q or not a:
            reason = "empty question or answer"
        elif not (MIN_Q <= len(q) <= MAX_Q):
            reason = f"question length {len(q)} out of [{MIN_Q},{MAX_Q}]"
        elif not (MIN_A <= len(a) <= MAX_A):
            reason = f"answer length {len(a)} out of [{MIN_A},{MAX_A}]"
        elif "?" not in q:
            reason = "question has no question mark"
        elif q.lower() in seen:
            reason = "duplicate question"
        else:
            # Citation/grounding check: the answer should touch the section's own
            # vocabulary, not drift into generic advice. Require at least one
            # non-trivial word (>=5 chars) shared with the section body.
            sec_words = {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{4,}", section["text"])}
            ans_words = {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{4,}", a)}
            if not (sec_words & ans_words):
                reason = "answer shares no vocabulary with the section (ungrounded)"
        if reason:
            rejected.append({**p, "source": section["source"], "reason": reason})
        else:
            seen.add(q.lower())
            kept.append({**p, "source": section["source"], "heading": section["heading"]})
    return kept, rejected


def to_chat(pair: dict) -> dict:
    """Emit one sample in the chat shape train_lora.py consumes — the SAME system
    prompt the server applies, so training and serving speak the same template."""
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": pair["question"]},
            {"role": "assistant", "content": pair["answer"]},
        ],
        "source": pair["source"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen3:0.6b")
    ap.add_argument("--corpus", default="labs/opsmate/corpus")
    ap.add_argument("--per-section", type=int, default=3)
    ap.add_argument("--max-sections", type=int, default=0)
    ap.add_argument("--eval-frac", type=float, default=0.1)
    ap.add_argument("--out-dir", default="labs/opsmate/train")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.corpus, "*.md")))
    if not files:
        print(f"no *.md under {args.corpus}", file=sys.stderr)
        sys.exit(1)

    sections = []
    for path in files:
        with open(path, "r", encoding="utf-8") as fh:
            sections.extend(split_sections(fh.read(), os.path.basename(path)))
    if args.max_sections:
        sections = sections[: args.max_sections]

    print(f"OpsMate synthetic data — {len(files)} runbooks, {len(sections)} sections")
    print(f"generator: {args.model} @ {OLLAMA_URL}  (think:false)")
    print(f"asking for {args.per_section} Q&A per section — this takes a few minutes on CPU\n")

    seen: set = set()
    kept_all, rejects_all = [], []
    for i, section in enumerate(sections, 1):
        try:
            raw = generate(args.model, section, args.per_section)
        except Exception as exc:  # noqa: BLE001 — one bad section must not kill the run
            print(f"  [{i}/{len(sections)}] {section['source']} :: {section['heading']}  ERROR {exc}")
            continue
        kept, rejected = filter_pairs(raw, section, seen)
        kept_all.extend(kept)
        rejects_all.extend(rejected)
        print(f"  [{i}/{len(sections)}] {section['source']} :: {section['heading'][:32]:<32} "
              f"+{len(kept)} kept  -{len(rejected)} rejected  (running total {len(kept_all)})")

    if not kept_all:
        print("\nno samples survived filtering — is Ollama serving the model?", file=sys.stderr)
        sys.exit(1)

    # Train/eval split. This eval slice is a LOSS sanity check during training —
    # it is NOT the golden set (that stays held out for the real measurement).
    rng = random.Random(args.seed)
    rng.shuffle(kept_all)
    n_eval = max(1, int(len(kept_all) * args.eval_frac))
    eval_rows, train_rows = kept_all[:n_eval], kept_all[n_eval:]

    os.makedirs(args.out_dir, exist_ok=True)
    train_path = os.path.join(args.out_dir, "train.jsonl")
    eval_path = os.path.join(args.out_dir, "eval.jsonl")
    rej_path = os.path.join(args.out_dir, "rejects.jsonl")
    for path, rows in ((train_path, train_rows), (eval_path, eval_rows)):
        with open(path, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(to_chat(r), ensure_ascii=False) + "\n")
    with open(rej_path, "w", encoding="utf-8") as fh:
        for r in rejects_all:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    meta = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": args.model,
        "sections": len(sections),
        "kept": len(kept_all),
        "rejected": len(rejects_all),
        "train": len(train_rows),
        "eval": len(eval_rows),
    }
    with open(os.path.join(args.out_dir, "synth-meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"\nkept {len(kept_all)} pairs, rejected {len(rejects_all)} "
          f"({100.0 * len(rejects_all) / max(1, len(kept_all) + len(rejects_all)):.0f}% filtered out)")
    print(f"  train: {len(train_rows)}  ->  {train_path}")
    print(f"  eval:  {len(eval_rows)}  ->  {eval_path}")
    print(f"  rejects (inspect these): {rej_path}")
    print("\nnext: uv run labs/m6/train_lora.py")


if __name__ == "__main__":
    main()
