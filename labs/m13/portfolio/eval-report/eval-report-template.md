# OpsMate Eval Report — v____ (fill in)

> Fill every blank from **your** capstone run. Do not invent numbers. If the candidate
> did not beat the baseline, say so — a BLOCK verdict is honest evidence the gate works,
> and reviewers respect it more than a suspiciously-green report.

## Run metadata

| Field | Value |
| --- | --- |
| Date | ____ |
| Candidate version | `1.2.0` |
| Baseline version | (the committed floor from `labs/opsmate/evals/baseline.md`) |
| Golden set | `labs/opsmate/evals/golden.yaml` (v1) |
| Answering model | `qwen3-0.6b` (tuned GGUF, CPU) |
| Gate | `labs/m12/eval-gate/gate.sh`, `FLOOR=____` |
| Host | ____ |

## The numbers

| Arm | Deterministic generation score | vs floor |
| --- | --- | --- |
| RAG (`/ask`, retrieval in path) | ____ / 12 | ____ |
| no-RAG control (retrieval stripped) | ____ / 12 | ____ |

## Gate verdict

- **Verdict:** `PROMOTE` / `BLOCK` (circle one — from `gate.sh`'s exit code)
- **Floor:** `>= ____ / 12` (from `baseline.md`)
- **What the verdict means:** ____

## What I learned (one honest paragraph)

Did the candidate beat the baseline? If not, why — knowledge loss, or an
answer-discipline shift on a small synthetic set (run the catastrophic-forgetting
probe to tell them apart)? What would you change before the next run? ____

## Signed artifact

The measured candidate is packaged as a signed ModelKit — see `../MODELKIT.md` for the
digest and the `cosign verify` command. The eval numbers above were measured on the
model *inside that kit*, so the report and the artifact are the same thing weighed and
sealed.
