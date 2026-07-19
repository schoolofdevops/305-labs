# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""Catastrophic-forgetting probe — did tuning cost the model its general knowledge?

Fine-tuning teaches new behaviour, but it can also OVERWRITE what the model
already knew — this is "catastrophic forgetting". A model tuned hard on your
narrow runbook voice can get worse at ordinary questions that have nothing to do
with runbooks. You should always check.

The probe: ask the SAME few general-knowledge questions to two OpenAI-compatible
endpoints — the base model and the tuned model — and read the answers side by
side. These questions are deliberately OUTSIDE the runbook domain, so a healthy
tuned model should still answer them about as well as the base. A tuned model
that has gone incoherent or wrong on them has forgotten too much — a signal to
tune more gently (lower rank, fewer epochs, mix in some general data).

This does not GRADE — it prints both answers for you to read (the honest,
human-in-the-loop check). Point --base-url and --tuned-url at two running
llama-server endpoints (bring the base up, capture; swap MODEL_GGUF, capture).

Usage:
  # with the base model served on :8080
  uv run labs/m6/forgetting_probe.py --which base
  # after swapping to the tuned GGUF (same port)
  uv run labs/m6/forgetting_probe.py --which tuned

Flags:
  --url      OpenAI-compatible base URL (default http://localhost:8080/v1)
  --model    model alias                (default qwen3-0.6b)
  --which    label for the output       (default current)
"""
import os
import argparse

import httpx

# Deliberately outside the SRE-runbook domain — this is what tuning must not break.
PROBES = [
    "In one sentence, what is the capital of Japan?",
    "In one sentence, what does the word 'ephemeral' mean?",
    "In one sentence, what is 17 multiplied by 4?",
]


def ask(url: str, model: str, question: str) -> str:
    resp = httpx.post(
        f"{url}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "temperature": 0.0,
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("MODEL_V1_URL", "http://localhost:8080/v1"))
    ap.add_argument("--model", default="qwen3-0.6b")
    ap.add_argument("--which", default="current")
    args = ap.parse_args()

    print(f"catastrophic-forgetting probe — {args.which} model @ {args.url}\n")
    for q in PROBES:
        try:
            a = ask(args.url, args.model, q)
        except Exception as exc:  # noqa: BLE001
            a = f"[error: {exc}]"
        # Collapse whitespace so a multi-line answer reads on one probe line.
        a = " ".join(a.split())
        print(f"  Q: {q}")
        print(f"  A: {a}\n")
    print("Read the base and tuned answers side by side: a tuned model that has gone")
    print("incoherent or wrong on these general questions has forgotten too much.")


if __name__ == "__main__":
    main()
