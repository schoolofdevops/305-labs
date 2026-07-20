# M3 lab assets — Serving Engines

These files back the M3 lab (**Two Engines, One Client, and a Load Test**) and
the deep dive. Run the lab from the rendered course page; this folder is what its
commands reference.

| File | What it is |
| --- | --- |
| `client.py` | The engine-swap exhibit. A one-file OpenAI-compatible chat client (`uv run client.py`). Point it at Ollama or llama-server with the one env var `OPENAI_BASE_URL` — the code never changes. |
| `loadtest.py` | Laptop-safe bounded load test (`uv run loadtest.py`). Sends a fixed request count at concurrency 4 → 8 → 16 against one engine; prints throughput and p50/p95 latency per level. Read the *shape*. |
| `checks.json` | Machine checks for the lab's success end-state (used by course validation). Self-seeds and self-cleans. |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page's end-state (prefix cache, metrics families). |

Both scripts are `uv`-runnable single files — `uv` reads the inline dependency
block and fetches what they need the first time. No virtualenv to manage.

## The compose spine lives in `labs/opsmate/`

M3 starts the OpsMate stack. The serving engine (llama-server) is defined in
`labs/opsmate/compose.yaml` — the first service of a file that grows every module
to M13. Bring it up with `make -C labs/opsmate up` (runs a preflight free-memory
and model-file check first) and down with `make -C labs/opsmate down`.

The model file itself (`labs/opsmate/models/gguf/qwen3-0.6b-q8_0.gguf`, ~610 MB)
is downloaded in Lab Step 1 and is gitignored — it is not shipped in the repo.
