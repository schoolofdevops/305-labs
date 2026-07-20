#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["openai>=1.40"]
# ///
"""OpsMate one-file chat client — the engine-swap exhibit.

The whole point of this script: it is written ONCE, against the OpenAI-compatible
/v1/chat/completions contract, and it does not know or care which engine answers.
Point it at Ollama or at llama-server by changing ONE environment variable
(OPENAI_BASE_URL). The code below never changes. That is the endpoint contract
from M2 made physical.

Run it:
    # against llama-server (the containerized engine, this module's compose spine)
    OPENAI_BASE_URL=http://localhost:8080/v1 MODEL=qwen3-0.6b uv run client.py

    # against Ollama (native on the host) — same script, one env var different
    OPENAI_BASE_URL=http://localhost:11434/v1 MODEL=qwen3:0.6b uv run client.py

    # ask your own question
    OPENAI_BASE_URL=http://localhost:8080/v1 MODEL=qwen3-0.6b \
      uv run client.py "How do I restart a wedged systemd unit?"
"""
import os
import sys

from openai import OpenAI

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
MODEL = os.environ.get("MODEL", "qwen3-0.6b")
# Local engines ignore the key, but the OpenAI client insists one is set.
API_KEY = os.environ.get("OPENAI_API_KEY", "not-needed-for-local")

PROMPT = " ".join(sys.argv[1:]) or "In one sentence, what does an SRE runbook contain?"


def main() -> None:
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
    print(f"engine  : {BASE_URL}")
    print(f"model   : {MODEL}")
    print(f"prompt  : {PROMPT}\n")

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are OpsMate, a concise SRE assistant. /no_think"},
            {"role": "user", "content": PROMPT},
        ],
        stream=False,
    )

    choice = resp.choices[0]
    print("answer  :", (choice.message.content or "").strip())
    print("finish  :", choice.finish_reason)
    usage = resp.usage
    if usage is not None:
        print(
            "usage   : prompt={} completion={} total={}".format(
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
            )
        )
        # Some engines report a prefix-cache hit here — tokens served from cache
        # instead of re-prefilled. llama-server surfaces it as cached_tokens.
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", None) if details else None
        if cached is not None:
            print(f"cached  : {cached} prompt tokens served from the prefix cache")


if __name__ == "__main__":
    main()
