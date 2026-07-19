#!/usr/bin/env python3
"""Tokenizer playground for M1 — How LLMs Work.

Run it with the course model's real tokenizer, no heavy install:

    uv run --with tokenizers labs/m1/tokens.py

The script needs Qwen3's tokenizer.json next to it. Step 2 of the lab fetches it:

    curl -L -o labs/m1/tokenizer.json \
      https://huggingface.co/Qwen/Qwen3-0.6B/resolve/main/tokenizer.json

Two jobs, both landing on an ops decision:
  1. Count tokens across English, Hindi, and code — see why the same idea costs
     a different number of tokens (tokens are the billing and capacity unit).
  2. Print the KV-cache memory table for a few context lengths — the number you
     size a GPU/box against before you ever deploy.

Nothing here talks to the network at runtime except the one-time tokenizer fetch
you do in the lab. The script only reads the local tokenizer.json.
"""

from __future__ import annotations

import os
import sys

# Qwen3-0.6B architecture facts (from its config.json). These drive the KV math.
# Qwen3-0.6B uses grouped-query attention: 28 layers, but only 8 key/value heads
# (not the 16 query heads). KV cache is sized by the KV heads, not the query heads.
MODEL_NAME = "Qwen3-0.6B"
N_LAYERS = 28
N_KV_HEADS = 8
HEAD_DIM = 128  # per-head dimension
BYTES_PER_ELEM = 2  # FP16/BF16 KV cache: 2 bytes per number

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENIZER_PATH = os.path.join(HERE, "tokenizer.json")

# Three samples that say roughly the same kind of thing in three "languages".
# The point is not translation accuracy — it is that the tokenizer splits each
# differently, so each costs a different number of tokens.
SAMPLES = {
    "english": "Restart the payment service and check the pod is running.",
    "hindi": "पेमेंट सेवा को फिर से चालू करो और पॉड चल रहा है यह देखो।",
    "code": 'kubectl rollout restart deployment/payments -n prod && kubectl get pods -l app=payments',
}


def load_tokenizer():
    try:
        from tokenizers import Tokenizer
    except ImportError:
        sys.exit(
            "The 'tokenizers' package is not available.\n"
            "Run this script with:  uv run --with tokenizers labs/m1/tokens.py"
        )
    if not os.path.exists(TOKENIZER_PATH):
        sys.exit(
            f"tokenizer.json not found at {TOKENIZER_PATH}\n"
            "Fetch it first (lab Step 2):\n"
            "  curl -L -o labs/m1/tokenizer.json \\\n"
            "    https://huggingface.co/Qwen/Qwen3-0.6B/resolve/main/tokenizer.json"
        )
    return Tokenizer.from_file(TOKENIZER_PATH)


def count_tokens(tok) -> None:
    print(f"== Token counts — {MODEL_NAME} tokenizer (BPE) ==\n")
    header = f"{'sample':<9}  {'chars':>6}  {'tokens':>7}  {'chars/token':>12}"
    print(header)
    print("-" * len(header))
    for name, text in SAMPLES.items():
        enc = tok.encode(text)
        n_tokens = len(enc.ids)
        n_chars = len(text)
        ratio = n_chars / n_tokens if n_tokens else 0.0
        print(f"{name:<9}  {n_chars:>6}  {n_tokens:>7}  {ratio:>12.2f}")
    print()
    # Show the first sample split into its actual pieces — the "word-pieces" you pay for.
    enc = tok.encode(SAMPLES["english"])
    pieces = [tok.decode([i]) for i in enc.ids]
    print("english, split into the pieces the model actually sees:")
    print("  " + " | ".join(repr(p) for p in pieces))
    print()
    print(
        "Same idea, three ways to write it — three different token counts. Tokens are\n"
        "what you are billed on and what fills the context window, not words or ideas.\n"
    )


def kv_cache_table() -> None:
    # KV cache bytes = 2 (K and V) * n_layers * n_kv_heads * head_dim
    #                  * bytes_per_elem * sequence_length
    per_token_bytes = 2 * N_LAYERS * N_KV_HEADS * HEAD_DIM * BYTES_PER_ELEM
    print(f"== KV-cache memory — {MODEL_NAME}, FP16 KV ==\n")
    print(
        f"Per token: 2 (K and V) into {N_LAYERS} layers into {N_KV_HEADS} KV-heads\n"
        f"           into {HEAD_DIM} head-dim into {BYTES_PER_ELEM} bytes\n"
        f"         = {per_token_bytes:,} bytes/token "
        f"({per_token_bytes / 1024:.1f} KiB/token)\n"
    )
    header = f"{'context (tokens)':>16}  {'KV cache':>12}  {'per concurrent request':>24}"
    print(header)
    print("-" * len(header))
    for ctx in (512, 2048, 8192, 32768):
        total = per_token_bytes * ctx
        mib = total / (1024 * 1024)
        print(f"{ctx:>16,}  {mib:>10.1f} MiB  {mib:>22.1f} MiB")
    print()
    print(
        "This is the number you size a box against. Ten users each holding an 8k\n"
        "context is ten into the 8k row — that memory is live the whole time they\n"
        "stay connected. On a bigger model the per-token cost is far higher, and this\n"
        "same table is how you decide how many concurrent users one GPU can hold.\n"
    )


def main() -> None:
    tok = load_tokenizer()
    count_tokens(tok)
    kv_cache_table()


if __name__ == "__main__":
    main()
