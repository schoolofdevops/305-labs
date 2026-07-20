# M5 lab assets — Prompts as Config & the Baseline Eval

These files back the M5 lab (**Prompts as Config & the Baseline Eval**) and its
Deep Dive. Run the lab from the rendered course page; this folder holds the runners
its commands reference. The golden set and the eval configs themselves live with the
stack in `labs/opsmate/evals/` (they are versioned artifacts the learner keeps).

| File | What it is |
| --- | --- |
| `retrieval_check.py` | The **retrieval-layer** runner (deterministic). Reads `golden.yaml`, hits the app's `/retrieve`, and checks the right source runbook is in top-k for every retrieval/generation question. Prints per-question PASS/FAIL + totals, writes `labs/opsmate/evals/retrieval-latest.json`, exits non-zero on any failure (so CI can gate). `uv run labs/m5/retrieval_check.py`. |
| `make_promptfoo_tests.py` | Regenerates `labs/opsmate/evals/generation-tests.yaml` from the canonical `golden.yaml`. Run it after editing the golden set so promptfoo and the golden set never drift. `uv run labs/m5/make_promptfoo_tests.py`. |
| `judge_agreement.py` | Deep-dive §2. Grades one fixed borderline answer with the local judge N times and reports self-agreement — the "smoke detector, not examiner" claim, measured. Needs only host Ollama. `uv run labs/m5/judge_agreement.py`. |
| `README.md` | This file. |
| `checks.json` | Machine checks for the lab's success end-state (course validation). Self-seeds (stack up + ingest if needed) and asserts shapes, not run-specific values. |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page's end-state (judge-agreement probe, Ragas-formula read-along, CI YAML present). |

## The eval artifacts live in `labs/opsmate/evals/`

The golden set and the runners' configs are versioned beside the stack because they
are course-long artifacts, not throwaway lab scratch:

- **`golden.yaml`** — the golden set v1. ~27 questions, every one authored FROM a
  corpus runbook (`source:` names it), split across three layers: `retrieval`
  (deterministic top-3 source check), `generation` (graded answer), and `honesty`
  (unanswerable-from-corpus — the model must admit the gap). This is the yardstick
  M6/M12/M13 all measure against.
- **`promptfooconfig.yaml`** — the **generation-layer** eval (RAG). Drives the app's
  `/ask`, grades answers with wide `contains-any` nets + a local `llm-rubric` judge
  (Ollama `qwen3:0.6b`). Run with
  `npx -y promptfoo@latest eval -c labs/opsmate/evals/promptfooconfig.yaml -o labs/opsmate/evals/generation-latest.json`.
- **`promptfooconfig-norag.yaml`** — the **no-RAG control arm**. Same questions and
  judge, but answers come straight from the base model on `/v1` with no retrieval.
  The gap between this and the RAG run is the measured value of retrieval.
- **`generation-tests.yaml`** — GENERATED from `golden.yaml` (do not hand-edit).
- **`baseline.md`** — the recorded, versioned baseline. The lab fills its placeholders
  with real numbers; that committed file is what M6 must beat.
- **`ci-preview.yml`** — a read-along GitHub Actions workflow (deep dive §4) showing the
  SHAPE of an eval gate. Preview only; M12 builds the real gate.

## The prompt is config now: `labs/opsmate/prompts/`

M5 externalizes the app's system prompt out of the code. `labs/opsmate/prompts/`
holds `system.txt` (v1, the M4 default) and `system-v2.txt` (the A/B variant). The
compose file mounts the directory read-only and points the app at it with
`SYSTEM_PROMPT_FILE`; swap the file + restart to A/B a prompt with zero code change,
and roll back by swapping it back (or `git checkout`). The app's `/prompt` endpoint
reports which prompt is loaded and a short fingerprint so a swap is inspectable.

## Requirements

`uv` runs the Python scripts (inline dependency blocks — no virtualenv). `node`
provides `npx` for promptfoo (no global install; first run downloads it once). The
local judge needs host Ollama serving `qwen3:0.6b` — `ollama pull qwen3:0.6b` once.
The stack must be up (`make -C labs/opsmate up`) and the index ingested for the RAG
arm; the golden set reuses the M4 Chroma index.
