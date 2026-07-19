# M6 lab assets — Fine-Tuning: Synthetic Data, LoRA & QLoRA

These files back the M6 lab (**Fine-Tuning**) and its Deep Dive. Run the lab from the
rendered course page; this folder holds the runners its commands reference. The
training artifacts they produce (adapter, merged model, tuned GGUF, progress logs)
land under `labs/opsmate/train/` and `labs/opsmate/models/gguf/` — beside the stack,
because M7 packages them.

| File | What it is |
| --- | --- |
| `synthesize.py` | Turns the runbook corpus into synthetic Q&A training data. Walks each `##` section, asks host Ollama (`qwen3:0.6b`, `think:false`) for a few grounded pairs, quality-filters (length + format + dedupe + grounding), and writes `train.jsonl` / `eval.jsonl` / `rejects.jsonl` in the app's chat format. **Reads only the corpus — never `golden.yaml`** (contamination rule). `uv run labs/m6/synthesize.py`. |
| `train_lora.py` | The LoRA fine-tune. Loads the base Qwen3-0.6B (fp32, CPU), attaches an `r=8 alpha=16` adapter on `q_proj,v_proj` (**0.19% / 1.15M trainable** — the lesson number), trains a few epochs over `train.jsonl`, writes `labs/opsmate/train/progress.jsonl` one line per step (`{step,loss,lr,elapsed_s}` — the X-Ray Train lens tails it), and saves the adapter to `labs/opsmate/train/adapter/`. `uv run labs/m6/train_lora.py`. |
| `merge_and_convert.py` | Merges the adapter into the base (`peft.merge_and_unload`) and converts the merged model to a `q8_0` GGUF with llama.cpp's `convert_hf_to_gguf.py` (shallow-cloned on first run into `.llama.cpp/`). Output: `labs/opsmate/models/gguf/opsmate-tuned-q8_0.gguf` — servable by the same llama-server, one filename change. `uv run labs/m6/merge_and_convert.py`. |
| `colab_qlora.ipynb` | Optional GPU enrichment track. A minimal QLoRA notebook (quantized base + LoRA on top) for a free Colab T4 — the same loop, one tier up. GPU-gated; see the honest availability note inside. |
| `README.md` | This file. |
| `checks.json` | Machine checks for the lab's success end-state (course validation). Heavy steps self-seed carefully; the training check asserts `progress.jsonl` exists and the last loss beats the first, rather than re-running a full train. |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page (rank/alpha table computable without training, chat-template demo, catastrophic-forgetting probe, Dockerfile present). |

## The pipeline, end to end

```
corpus/*.md                        (the source material — the "textbook")
   │  synthesize.py  (host Ollama, generate → filter → split)
   ▼
labs/opsmate/train/train.jsonl     (chat-format Q&A — the "practice question bank")
   │  train_lora.py  (LoRA r=8, fp32 CPU, ~minutes)
   ▼
labs/opsmate/train/adapter/        (4-5 MB removable fittings + progress.jsonl)
   │  merge_and_convert.py  (peft merge → llama.cpp convert → q8_0)
   ▼
labs/opsmate/models/gguf/opsmate-tuned-q8_0.gguf   (servable, ~767 MB)
   │  MODEL_GGUF=opsmate-tuned-q8_0.gguf make -C labs/opsmate up
   ▼
the SAME llama-server serves the tuned model — re-run the M5 golden set, MEASURE
```

## The contamination rule (why this matters)

The M5 golden set (`labs/opsmate/evals/golden.yaml`) is the **held-out test set** — the
yardstick M6 must beat. `synthesize.py` therefore reads **only** `labs/opsmate/corpus/`,
never `golden.yaml`. The synthetic questions share the same *sources* as the golden set
(the same runbooks) but are freshly generated and quality-filtered; the golden set stays
untouched and is what we measure against at the end. Training on your test set inflates
every number that follows — the whole point of the M5 baseline is that this line is real.

## The switchable served model

M6 makes the compose `model` service's GGUF file switchable via `${MODEL_GGUF:-...}`:

```bash
# base (default) — the M0–M5 model
make -C labs/opsmate up
# tuned — the M6 output, one env var, no code change
MODEL_GGUF=opsmate-tuned-q8_0.gguf make -C labs/opsmate up
```

`/v1/models` and the app's answers reflect whichever file you served. This is the
model-swap-by-filename story M3 set up (OpenAI-compatible endpoint, backend swappable)
now carrying a model you trained yourself — and the v0-base / v1.0-tuned pair M7 versions.

## Requirements

`uv` runs every Python script from its inline dependency block — no virtualenv. The
first `train_lora.py` / `merge_and_convert.py` run downloads ~2 GB of torch (once).
`synthesize.py` and the merge step need host Ollama serving `qwen3:0.6b`
(`ollama pull qwen3:0.6b`). The GGUF conversion shallow-clones llama.cpp (needs `git`).
Run the training with the OpsMate stack **down** — training wants the RAM the stack was
using (the one-stack-at-a-time rule, applied to training).
