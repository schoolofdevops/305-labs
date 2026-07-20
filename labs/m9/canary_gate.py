# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "pyyaml"]
# ///
"""OpsMate canary quality gate — the module's climax, in one thin script.

A readiness probe cannot taste the food. The pod is `1/1 Running` and the canary
answers every request without error — and it is STILL the wrong model, because
"answers without crashing" and "answers correctly" are different signals. This
gate measures the second one. It runs the SAME golden set that set the M5
baseline and rejected the tune in M6, now pointed at the two live backends, and
turns the verdict into a data-driven PROMOTE or ROLLBACK.

WHAT IT DOES (deliberately the simplest honest gate):
  1. Load the golden generation questions (layer == generation) from golden.yaml.
  2. For each, hit the CANARY Service /v1/chat/completions directly and the BASE
     Service directly — same question, same decoding, one backend each.
  3. Score each answer with the golden set's OWN wide `contains_any` nets (the M5
     discipline: a small model paraphrases, so assert the right THING is named,
     in any of several wordings — not an exact phrase).
  4. Compare pass-counts. The candidate must at LEAST TIE the base to promote;
     if it scores fewer, the verdict is ROLLBACK.

This is a spot-run, not the full graded eval. It hits the models DIRECTLY (no RAG
app in the loop), so it measures the model's own generation the way M6's no-RAG
arm did — which is exactly why the M6 loser loses here too. It runs against the
canary's own Service (opsmate-canary), reached through a port-forward the lab
opens; the same pattern points at the base (opsmate-model). Exit code is 0 on
PROMOTE, 1 on ROLLBACK — so M12's CI can gate promotion on this directly.

Usage (the lab port-forwards both Services to local ports first):
  uv run labs/m9/canary_gate.py \
      --base   http://127.0.0.1:8091/v1 \
      --canary http://127.0.0.1:8092/v1 \
      --n 6

Flags:
  --base     base backend /v1 base URL        (default http://127.0.0.1:8091/v1)
  --canary   canary backend /v1 base URL      (default http://127.0.0.1:8092/v1)
  --golden   path to golden.yaml              (default labs/opsmate/evals/golden.yaml)
  --n        how many generation questions to spot-run (default 6; 0 = all)
  --model    model name to send               (default qwen3-0.6b — both aliases match)
"""
import os
import sys
import argparse

import httpx
import yaml


def complete(base_url: str, model: str, question: str) -> str:
    """One completion, greedy, so the comparison is about the model, not sampling."""
    resp = httpx.post(
        f"{base_url}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "temperature": 0.0,
            # The base (1.0.0) is a REASONING model: it spends tokens in a
            # <think> pass (returned as reasoning_content) before it writes the
            # actual answer into content. At a tight budget it hits the cap mid-
            # think and returns an EMPTY content — scoring 0 on every net even
            # though it "answered". The candidate was tuned to answer directly, so
            # a low cap silently rigs the gate toward the candidate (a false
            # PROMOTE). Give both models room to finish so the comparison is about
            # quality, not who reasons less.
            "max_tokens": 1024,
        },
        timeout=180.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def scores(answer: str, contains_any: list[str]) -> bool:
    """The golden set's wide net: any one substring present = a grounded answer."""
    low = answer.lower()
    return any(s.lower() in low for s in contains_any)


def run_arm(name: str, base_url: str, model: str, questions: list[dict]) -> int:
    print(f"\n=== {name}  ({base_url}) ===")
    passed = 0
    for q in questions:
        try:
            answer = complete(base_url, model, q["question"])
        except Exception as exc:  # noqa: BLE001 — surface transport errors per-question
            print(f"  ERROR {q['id']:<26} {exc}")
            continue
        ok = scores(answer, q.get("contains_any", []))
        passed += int(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {q['id']:<26} "
              f"(net: {'|'.join(q.get('contains_any', []))})")
    return passed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8091/v1")
    ap.add_argument("--canary", default="http://127.0.0.1:8092/v1")
    ap.add_argument("--golden", default="labs/opsmate/evals/golden.yaml")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--model", default="qwen3-0.6b")
    args = ap.parse_args()

    with open(args.golden, "r", encoding="utf-8") as fh:
        golden = yaml.safe_load(fh)

    gen = [q for q in golden["questions"] if q.get("layer") == "generation"]
    if args.n > 0:
        gen = gen[: args.n]

    print(f"OpsMate canary quality gate — {len(gen)} generation questions, "
          f"direct /v1 spot-run (no RAG)")
    print(f"base   : {args.base}")
    print(f"canary : {args.canary}")

    base_pass = run_arm("BASE  (opsmate-model, 1.0.0)", args.base, args.model, gen)
    canary_pass = run_arm("CANARY (opsmate-canary, 1.0.0-candidate)",
                          args.canary, args.model, gen)

    total = len(gen)
    print("\n" + "=" * 52)
    print(f"BASE    passed {base_pass}/{total}")
    print(f"CANARY  passed {canary_pass}/{total}")

    # The gate: the candidate must at least tie the base to earn promotion. It is
    # replacing a model that already works — "no worse" is the floor, and the M6
    # loser does not clear it.
    if canary_pass >= base_pass:
        print(f"\nVERDICT: PROMOTE — canary ({canary_pass}) >= base ({base_pass}); "
              f"the candidate holds or improves quality.")
        sys.exit(0)
    else:
        print(f"\nVERDICT: ROLLBACK — canary ({canary_pass}) < base ({base_pass}); "
              f"the candidate regresses quality. Set its weight to 0 and restart the router.")
        sys.exit(1)


if __name__ == "__main__":
    main()
