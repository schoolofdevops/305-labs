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
