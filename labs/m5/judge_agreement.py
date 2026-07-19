# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""Measure how much the local judge agrees with ITSELF.

The deep dive's honesty beat, made concrete. A judge model is a fallible model:
ask it to grade the same (answer, rubric) pair twice and it may not give the same
verdict. This script does exactly that — it sends one fixed grading prompt to the
local Ollama judge N times and reports how often the PASS/FAIL verdict agrees with
the majority. Low self-agreement is the number that tells you how much to trust any
single grade — the reason a 0.6B judge is a smoke detector, not an examiner.

This does NOT need the OpsMate stack — only host Ollama serving the judge model. It
grades a fixed, deliberately-borderline answer so the disagreement is visible.

Usage:
  uv run labs/m5/judge_agreement.py
  uv run labs/m5/judge_agreement.py --runs 10 --temperature 0

Env:
  OLLAMA_URL   host Ollama base URL   (default http://localhost:11434)
  JUDGE_MODEL  the judge model        (default qwen3:0.6b)
"""
import os
import re
import argparse

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3:0.6b")

# A deliberately BORDERLINE case: the answer is partly right (names the pool) but
# vague about the check — the kind of answer honest judges can split on.
RUBRIC = (
    "The answer must identify database connection-pool exhaustion as the likely "
    "cause of the payments-api 5xx errors AND point at a concrete check (the "
    "db_pool_in_use gauge). A vague mention of 'the pool' without the concrete "
    "check should FAIL."
)
ANSWER = "It's probably something to do with the connection pool on the payments service."

GRADE_PROMPT = (
    "You are grading an assistant's answer against a rubric. Reply with exactly one "
    "word on the first line: PASS or FAIL.\n\n"
    f"RUBRIC:\n{RUBRIC}\n\nANSWER:\n{ANSWER}\n\nVerdict:"
)


def grade_once(temperature: float) -> str:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": JUDGE_MODEL,
            "messages": [{"role": "user", "content": GRADE_PROMPT}],
            "stream": False,
            "think": False,
            "options": {"temperature": temperature},
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    text = resp.json()["message"]["content"].upper()
    # First PASS/FAIL token wins.
    m = re.search(r"\b(PASS|FAIL)\b", text)
    return m.group(1) if m else "UNPARSEABLE"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    print(f"judge: {JUDGE_MODEL} @ {OLLAMA_URL}  (temperature {args.temperature})")
    print(f"grading the SAME borderline answer {args.runs} times...\n")

    verdicts = []
    for i in range(args.runs):
        v = grade_once(args.temperature)
        verdicts.append(v)
        print(f"  run {i + 1:>2}: {v}")

    passes = verdicts.count("PASS")
    fails = verdicts.count("FAIL")
    majority = "PASS" if passes >= fails else "FAIL"
    agree = max(passes, fails)
    pct = round(100.0 * agree / len(verdicts), 1)
    print(f"\nverdicts: {passes} PASS / {fails} FAIL"
          + (f" / {verdicts.count('UNPARSEABLE')} unparseable" if "UNPARSEABLE" in verdicts else ""))
    print(f"self-agreement with the majority ({majority}): {agree}/{len(verdicts)} = {pct}%")
    if pct < 100.0:
        print("\nThe judge disagrees with itself on a borderline answer — this is the")
        print("noise the 'smoke detector, not examiner' framing is about. A single grade")
        print("on a marginal answer is not ground truth; corroborate with the")
        print("deterministic retrieval layer and, in production (M12), a stronger judge.")
    else:
        print("\nFully consistent on THIS run — try --temperature 0.4, or a genuinely")
        print("borderline answer, to surface the disagreement a small judge carries.")


if __name__ == "__main__":
    main()
