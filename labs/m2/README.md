# M2 lab assets — Models, Quantization & the OpenAI-Compatible Contract

These files back the M2 lab (**Two Quants Side by Side, and the Raw API Tour**).
Run the lab from the rendered course page; this folder is what its commands reference.

| File | What it is |
| --- | --- |
| `Makefile` | `make up` checks Ollama is running and the Q4 course model `qwen3:0.6b` is pulled. `make down` removes the M2-only `qwen3:0.6b-q8_0` quant to reclaim ~832 MB; the Q4 model stays for M3. |
| `checks.json` | Machine checks for the lab's success end-state (used by course validation). Self-seeds the Q8 quant where a check needs it and cleans up after. |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page's end-state (quant families, context economics, licence, API drift). |

This lab is mostly `ollama`, `curl`, and `jq` — no helper script. The one extra
download is the second quant, `qwen3:0.6b-q8_0` (about 832 MB), pulled in Step 2
and removed in Teardown.

Ollama runs **native** on the host in M1–M2 (the Apple Silicon pattern, explained in M3).
The growing `labs/opsmate/` container stack begins in M3.
