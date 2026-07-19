# OpsMate Baseline — Golden Set v1 (course reference run)

**This file is the yardstick.** The numbers below are the defensible baseline that
the rest of the course measures against:

- **M6** fine-tunes OpsMate's model and **must beat** these numbers to justify shipping.
- **M12** wires the golden set into a CI gate and **promotes only if** a change holds
  or improves them.
- **M13** replays this exact set against the production capstone.

A baseline is worthless unless it is *recorded* and *versioned*. That is why this is
a committed file, not a screenshot in a chat. This copy is the **course reference run**
(the validated numbers M6 must beat). In the lab you record YOUR OWN run in
`baseline-mine.md` from the blank template — do not invent numbers, and keep the run
metadata so a future you can reproduce it.

> Point-in-time: these numbers come from one run on one machine with a 0.6B model on
> CPU. Absolute scores are modest and will differ on your hardware and as models
> change. What matters is the **gap** between arms (RAG beats no-RAG) and that later
> stages **move the numbers in the right direction** against the same set.

## Run metadata

| Field | Value |
| --- | --- |
| Date | 2026-07-20 |
| Golden set | `labs/opsmate/evals/golden.yaml` (v1) |
| Questions | 12 retrieval · 12 generation · 3 honesty (24 scored by retrieval, 15 by generation) |
| Answering model | `qwen3-0.6b` (llama-server, CPU) |
| Judge model | `qwen3:0.6b` via Ollama (local — smoke detector, not examiner) |
| Embedding model | `nomic-embed-text` (768-dim) |
| Host | Apple Silicon Mac, Rancher Desktop (Moby/dockerd) |

## Layer 1 — Retrieval (deterministic, `retrieval_check.py`)

The right source runbook in top-3. RAG only (no-RAG has no retrieval step).

| Arm | Passed / Total | % |
| --- | --- | --- |
| RAG (`/ask` app, top-3) | 24 / 24 | 100% |

_Per-question failures, if any (id → what got retrieved instead):_

- None — all 24 land their source runbook at rank 1.

## Layer 2 — Generation (graded, promptfoo: contains-any + local rubric)

Same 15 graded questions (12 generation + 3 honesty), two arms.

| Arm | Passed / Total | % | Config |
| --- | --- | --- | --- |
| **No-RAG** (base model, direct `/v1`) | 3 / 15 | 20.0% | `promptfooconfig-norag.yaml` |
| **RAG** (`/ask`, retrieved context) | 6 / 15 | 40.0% | `promptfooconfig.yaml` |

**The gap (RAG − no-RAG):** +20 percentage points (20% → 40%). This is the measured
value of retrieval on this set — the RAG arm doubles the base model's pass rate.

### Honesty sub-score (the 3 unanswerable questions)

| Arm | Honestly refused / 3 |
| --- | --- |
| No-RAG (base model) | 0 / 3 |
| RAG (`/ask`) | 0 / 3 |

_Both arms read 0/3 — and per-question inspection shows a **mix of two causes across
runs**: on some questions the model refuses correctly and the local 0.6B `llm-rubric`
judge fails the refusal while quoting the very rubric that says refusing is correct (a
judge artifact); on other runs the model genuinely bluffs an answer and the FAIL is
real signal. Only the ten-second `jq` inspect distinguishes the two — which is exactly
the "smoke detector, not examiner" lesson. M12 upgrades the judge; the defensible
signal in this baseline is the generation gap above, not the honesty count._

## Layer 3 — Prompt A/B (system.txt vs system-v2.txt), RAG arm

Same suite, same code — only the mounted prompt file changed.

| Prompt | Generation passed / 15 | % | Honesty refused / 3 |
| --- | --- | --- | --- |
| `system.txt` (v1) | 6 / 15 | 40.0% | 0 / 3 |
| `system-v2.txt` (v2) | 5 / 15 | 33.3% | 0 / 3 |

_One line on what moved and why — the prompt change altered scores with the code
untouched, which is the "prompts as config" point made measurable:_

- v2 (the longer, more explicit "always cite the runbook / admit gaps" prompt) scored
  **5/15 — below v1's 6/15.** The fancier prompt did **not** beat the simpler one on
  this judge; retrieval quality and judge noise dominate the score here. The lesson is
  the discipline (swap a file, measure, un-pull the lever), not the direction of the
  number. **v1 is retained** as the recorded baseline.

## Verdict

- Baseline recorded: yes
- RAG beats no-RAG on generation: yes (6/15 vs 3/15, +20 pts — as expected)
- This file is committed to the repo as the number M6 must beat: yes — **M6 must beat
  6/15 (40%) generation / 24/24 retrieval on this same golden set.**

## M6 — Tuned model measured against this baseline (course reference run)

M6 fine-tunes OpsMate's model (LoRA `r=8`, 2 epochs, 185 synthetic pairs on the
0.6B base) and measures the tuned model on this **exact** golden set. Run date
2026-07-20, same host/embedding config as above — and critically the **same judge
held constant** (`qwen3:0.6b` via Ollama), so any score change reflects the *answering*
model, not the grader. The tuned GGUF was served via the compose swap
(`MODEL_GGUF=opsmate-tuned-q8_0.gguf`).

| Arm | Tuned | Baseline (above) | Δ | Verdict |
| --- | --- | --- | --- | --- |
| Retrieval (control) | 24 / 24 (100%) | 24 / 24 | 0 | Unchanged — retrieval is model-independent |
| Generation, RAG | **2 / 15 (13.3%)** | 6 / 15 (40%) | **−4 (−26.7 pts)** | **LOST** |
| Generation, no-RAG | **1 / 15 (6.7%)** | 3 / 15 (20%) | **−2 (−13.3 pts)** | **LOST** |

**Verdict: the tuned model did NOT beat the baseline — not shipped.** It regressed
both graded generation arms while the control held. Catastrophic-forgetting probe was
clean (general knowledge intact — capital of Japan, 'ephemeral', 17×4 all correct on
the tuned model), so the regression is a behaviour/answer-discipline shift on the small
synthetic set, not knowledge loss. This is the intended teaching outcome: the committed
baseline did its job as a yardstick and refused a model that would have regressed
quality. **The gate works.** M12 automates exactly this comparison as a CI promotion
gate. Tuned eval artifacts: `generation-tuned-latest.json` (RAG),
`generation-tuned-norag.json` (no-RAG).
