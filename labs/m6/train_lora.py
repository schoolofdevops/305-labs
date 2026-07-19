# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch",
#   "transformers>=4.51",
#   "peft",
#   "accelerate",
#   "datasets",
# ]
# ///
"""OpsMate LoRA fine-tune — the removable-fittings adapter, on CPU, in minutes.

The analogy: the base model is a rented building whose walls you cannot touch
(the frozen weights). LoRA lets you renovate with REMOVABLE FITTINGS — a small
low-rank adapter bolted alongside the frozen weights. You train only the
fittings (~0.19% of the parameters here), and when you are done you can leave
them merged into the building or unbolt them and carry them somewhere else. That
tiny, swappable footprint is the whole reason LoRA fits on a laptop and the
reason M7 can PACKAGE the adapter as its own versioned artifact.

What this script does:
  1. Load the base Qwen3-0.6B (local safetensors) in fp32 on CPU.
  2. Attach a LoRA adapter: r=8, alpha=16, on q_proj + v_proj (the spike config).
     It prints the trainable-parameter line — ~1.15M of ~597M = 0.19%.
  3. Train on the chat-format JSONL from synthesize.py for a few epochs, batch 2.
  4. Write labs/opsmate/train/progress.jsonl — one line PER STEP
     {step, loss, lr, elapsed_s} — which the X-Ray Train lens tails live.
  5. Save the adapter to labs/opsmate/train/adapter/ (merge happens in
     merge_and_convert.py — this script only trains the fittings).

Deps download ~2 GB of torch the first run (Troubleshooting note in the lab).
CPU fp32 is deliberate: on the 8 GB path a GPU/quantized stack is not assumed,
and the spike measured 0.5 s/step here — a real ~300-sample, 2-epoch run is
minutes, not hours.

Usage:
  uv run labs/m6/train_lora.py
  uv run labs/m6/train_lora.py --epochs 2 --max-steps 3   # smoke: 3 steps only
  uv run labs/m6/train_lora.py --base labs/opsmate/models/qwen3-0.6b

Flags:
  --base        base model dir      (default labs/opsmate/models/qwen3-0.6b)
  --train       train jsonl         (default labs/opsmate/train/train.jsonl)
  --out-dir     adapter + logs dir  (default labs/opsmate/train)
  --epochs      passes over data    (default 2)
  --batch       per-device batch    (default 2)
  --lr          learning rate       (default 2e-4)
  --rank        LoRA r              (default 8)
  --alpha       LoRA alpha          (default 16)
  --max-len     max sequence length (default 512)
  --max-steps   hard step cap       (default 0 = full run; use 3 for a smoke test)
  --seed        RNG seed            (default 13)
"""
import os
import sys
import json
import time
import argparse

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    TrainerCallback,
    DataCollatorForLanguageModeling,
)
from peft import LoraConfig, get_peft_model


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


class ProgressCallback(TrainerCallback):
    """Append one JSON line per optimizer step to progress.jsonl — the exact file
    the X-Ray Train lens tails. Kept dead simple (append-only, flush each line) so
    the lens can read it WHILE training is still running."""

    def __init__(self, path: str):
        self.path = path
        self.start = time.time()
        # Truncate at the start of a run so an old curve is not tailed as the new one.
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("")

    def on_log(self, args, state, control, logs=None, **kwargs):
        if not logs or "loss" not in logs:
            return
        record = {
            "step": int(state.global_step),
            "loss": round(float(logs["loss"]), 4),
            "lr": float(logs.get("learning_rate", 0.0)),
            "elapsed_s": round(time.time() - self.start, 1),
        }
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
            fh.flush()
        print(f"  step {record['step']:>4}  loss {record['loss']:.4f}  "
              f"lr {record['lr']:.2e}  {record['elapsed_s']:.1f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="labs/opsmate/models/qwen3-0.6b")
    ap.add_argument("--train", default="labs/opsmate/train/train.jsonl")
    ap.add_argument("--out-dir", default="labs/opsmate/train")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=8)
    ap.add_argument("--alpha", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    if not os.path.isfile(args.train):
        print(f"no training file at {args.train} — run synthesize.py first", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    progress_path = os.path.join(args.out_dir, "progress.jsonl")
    adapter_dir = os.path.join(args.out_dir, "adapter")

    print(f"OpsMate LoRA fine-tune — base {args.base}")
    print(f"  device: CPU (fp32)  |  r={args.rank} alpha={args.alpha} target=q_proj,v_proj")
    t0 = time.time()

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.float32)
    model.config.use_cache = False  # required with gradient flow through the adapter

    lora = LoraConfig(
        r=args.rank,
        lora_alpha=args.alpha,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    # THE LoRA LESSON, printed: trainable params vs total. On this base/config it
    # reads ~1,146,880 trainable of ~597M total = 0.19%. Tiny is the point.
    model.print_trainable_parameters()
    print(f"    model loaded in {time.time() - t0:.1f}s")

    # --- build the tokenized dataset from the chat samples -------------------
    # Apply the SAME chat template the server uses so training and inference speak
    # the same format (the chat-template pitfall — see the deep dive). We train on
    # the full rendered conversation (system+user+assistant) as a causal LM target.
    rows = load_jsonl(args.train)
    print(f"    {len(rows)} training samples from {args.train}")

    def render(example):
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )
        enc = tokenizer(text, truncation=True, max_length=args.max_len, padding=False)
        return enc

    ds = Dataset.from_list(rows).map(render, remove_columns=["messages", "source"])
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    train_args = TrainingArguments(
        output_dir=os.path.join(args.out_dir, "hf-checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        learning_rate=args.lr,
        logging_steps=1,          # one progress.jsonl line per step
        save_strategy="no",       # we save the adapter ourselves at the end
        max_steps=args.max_steps if args.max_steps else -1,
        report_to=[],             # no wandb/tensorboard on the laptop path
        seed=args.seed,
        use_cpu=True,
        dataloader_num_workers=0,
    )

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=ds,
        data_collator=collator,
        callbacks=[ProgressCallback(progress_path)],
    )

    print(f"\n  training — watch {progress_path} (the X-Ray Train lens tails it)\n")
    result = trainer.train()

    # Persist the adapter (the removable fittings) — NOT merged. merge happens next.
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    losses = [json.loads(l)["loss"] for l in open(progress_path) if l.strip()]
    summary = {
        "base": args.base,
        "adapter_dir": adapter_dir,
        "samples": len(rows),
        "epochs": args.epochs,
        "steps": len(losses),
        "first_loss": losses[0] if losses else None,
        "last_loss": losses[-1] if losses else None,
        "train_runtime_s": round(result.metrics.get("train_runtime", time.time() - t0), 1),
    }
    with open(os.path.join(args.out_dir, "train-summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"\n  done — {summary['steps']} steps, "
          f"loss {summary['first_loss']} -> {summary['last_loss']} "
          f"in {summary['train_runtime_s']}s")
    print(f"  adapter saved to {adapter_dir}")
    print("\nnext: uv run labs/m6/merge_and_convert.py")


if __name__ == "__main__":
    main()
