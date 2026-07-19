# OpsMate Baseline — MY run

Copy of the baseline template. Fill every `___` from YOUR real runs — do not invent
numbers. Compare with the committed course reference run in `baseline.md`; your
absolute numbers will differ (hardware, judge noise), the shape should match
(retrieval near-perfect, RAG beats no-RAG).

## Run metadata

| Field | Value |
| --- | --- |
| Date | ___ |
| Answering model | ___ |
| Judge model | ___ |
| Host | ___ |

## Layer 1 — Retrieval

| Arm | Passed / Total | % |
| --- | --- | --- |
| RAG (`/ask` app, top-3) | ___ / 24 | ___% |

## Layer 2 — Generation

| Arm | Passed / Total | % |
| --- | --- | --- |
| No-RAG (base model, direct `/v1`) | ___ / 15 | ___% |
| RAG (`/ask`, retrieved context) | ___ / 15 | ___% |

**The gap (RAG − no-RAG):** ___ points.

### Honesty sub-score

| Arm | Honestly refused / 3 | Cause per `jq` inspect (judge artifact / real bluff) |
| --- | --- | --- |
| No-RAG | ___ / 3 | ___ |
| RAG | ___ / 3 | ___ |

## Layer 3 — Prompt A/B (RAG arm)

| Prompt | Passed / 15 | % |
| --- | --- | --- |
| `system.txt` (v1) | ___ / 15 | ___% |
| `system-v2.txt` (v2) | ___ / 15 | ___% |

Which prompt do you retain, and why: ___

## M6 — Tuned model vs baseline (fill after the fine-tune)

Serve the tuned GGUF (`MODEL_GGUF=opsmate-tuned-q8_0.gguf`) and re-run the SAME golden
set. Fill every `___` from your real tuned-model runs. The retrieval layer is the
CONTROL — it should be unchanged (tuning changed the model, not the index).

### Retrieval (control — expect unchanged from M5)

| Arm | Passed / Total | % |
| --- | --- | --- |
| Tuned + RAG (`/ask`, top-3) | ___ / 24 | ___% |

Did retrieval change from your M5 baseline? ___ (if yes, that is a bug — find it before trusting the rest)

### Generation (tuned model, two arms)

| Arm | Passed / 15 | % | vs M5 baseline |
| --- | --- | --- | --- |
| Tuned + RAG (`generation-tuned-latest.json`) | ___ / 15 | ___% | ___ pts (M5 RAG was 6/15) |
| Tuned, no-RAG direct (`generation-tuned-norag.json`) | ___ / 15 | ___% | ___ pts (M5 no-RAG was 3/15) |

### Read the outcome with the honesty rule

Which outcome did you get — **beat**, **tie**, or **lose** vs the M5 RAG baseline? ___

One honest sentence on what it means (tuning answers voice/format problems, RAG answers
knowledge problems; the golden set grades knowledge-grounded answers). What does this
number measure, and what does it NOT measure? ___
