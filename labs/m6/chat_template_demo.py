# /// script
# requires-python = ">=3.10"
# dependencies = ["transformers>=4.51", "jinja2"]
# ///
"""Chat-template demo — why train and serve MUST share the template.

The single most common way a fine-tune quietly fails: you train on one text
format and the server wraps the prompt in a DIFFERENT format at inference. The
model then sees, at serve time, tokens it never saw in training — the special
role markers, the turn boundaries — and the tuning does not transfer. It is the
"studied for the wrong exam format" failure: you learned the material, but the
paper is laid out differently and you freeze.

This script prints, for one sample conversation, TWO renderings:
  1. The model's OWN chat template (what apply_chat_template produces) — the
     format llama-server also applies at serve time, full of <|im_start|> markers.
  2. A naive "Q: ... A: ..." concatenation — a plausible-looking but WRONG format
     a hand-rolled trainer might use.

Read them side by side. train_lora.py uses rendering #1 on purpose, so the model
trains on exactly the tokens the server will feed it. If you had trained on #2,
the adapter would be tuned for markers the server never emits — a silent miss.

Usage:
  uv run labs/m6/chat_template_demo.py
  uv run labs/m6/chat_template_demo.py --base labs/opsmate/models/qwen3-0.6b
"""
import argparse

from transformers import AutoTokenizer

SAMPLE = [
    {"role": "system", "content": "You are OpsMate, an SRE assistant."},
    {"role": "user", "content": "the payments api is throwing 500s, what is the most likely cause"},
    {"role": "assistant", "content": "Database connection-pool exhaustion — check db_pool_in_use."},
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="labs/opsmate/models/qwen3-0.6b")
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.base)

    correct = tok.apply_chat_template(SAMPLE, tokenize=False, add_generation_prompt=False)
    naive = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in SAMPLE
    )

    print("=" * 70)
    print("1. CORRECT — the model's own chat template (train AND serve use this):")
    print("=" * 70)
    print(correct)
    print("=" * 70)
    print("2. WRONG — a naive Q/A concatenation a hand-rolled trainer might use:")
    print("=" * 70)
    print(naive)
    print("=" * 70)
    print("\nThe difference is the point. The server emits the special role markers")
    print("from #1 at inference. Train on #2 and the model never learns them — the")
    print("tuning does not transfer. train_lora.py renders #1 for exactly this reason.")


if __name__ == "__main__":
    main()
