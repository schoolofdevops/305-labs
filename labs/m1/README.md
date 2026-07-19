# M1 lab assets — How LLMs Work

These files back the M1 lab (**How LLMs Work — Tokens, Prefill/Decode & the KV Cache**).
Run the lab from the rendered course page; this folder is what its commands reference.

| File | What it is |
| --- | --- |
| `tokens.py` | Tokenizer playground. Counts tokens across English/Hindi/code with the real Qwen3 tokenizer and prints the KV-cache memory table. Run: `uv run --with tokenizers labs/m1/tokens.py` |
| `Makefile` | `make up` checks Ollama is running and `qwen3:0.6b` is pulled. `make down` is a no-op note (Ollama is native, no containers in M1). |
| `checks.json` | Machine checks for the lab's success end-state (used by course validation). |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page's end-state. |

`tokenizer.json` is fetched during the lab (Step 2) and is not committed here.

Ollama runs **native** on the host in M1–M2 (the Apple Silicon pattern, explained in M3).
The growing `labs/opsmate/` container stack begins in M3.

The live visualizer for this course is `labs/tools/xray/` — the Tokens lens lands with M1.
Run it with `bash labs/tools/xray/serve.sh`.
