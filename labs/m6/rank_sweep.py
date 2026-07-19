# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch",
#   "transformers>=4.51",
#   "peft",
# ]
# ///
"""Rank sweep — what does r actually buy? Trainable-% for r=4/8/16/32, no training.

The deep-dive question is "how big should the adapter be?" You do not need to
train to answer the first half — the trainable-parameter count is a pure function
of the rank, the alpha, and which modules you target. This script attaches a LoRA
at each rank to the real base model and prints the trainable-parameter table, so
you can SEE the linear growth (double the rank, double the adapter) and decide
where the diminishing returns start for your model — all in seconds, no GPU, no
optimizer step.

Usage:
  uv run labs/m6/rank_sweep.py
  uv run labs/m6/rank_sweep.py --targets q_proj v_proj k_proj o_proj

Flags:
  --base     base model dir   (default labs/opsmate/models/qwen3-0.6b)
  --ranks    ranks to sweep   (default 4 8 16 32)
  --alpha    LoRA alpha       (default 16 — held fixed so rank is the only variable)
  --targets  modules to adapt (default q_proj v_proj)
"""
import argparse

import torch
from transformers import AutoModelForCausalLM
from peft import LoraConfig, get_peft_model


def trainable_counts(base: str, rank: int, alpha: int, targets: list[str]) -> tuple[int, int]:
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float32)
    lora = LoraConfig(r=rank, lora_alpha=alpha, target_modules=targets,
                      lora_dropout=0.0, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    del model
    return trainable, total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="labs/opsmate/models/qwen3-0.6b")
    ap.add_argument("--ranks", type=int, nargs="+", default=[4, 8, 16, 32])
    ap.add_argument("--alpha", type=int, default=16)
    ap.add_argument("--targets", nargs="+", default=["q_proj", "v_proj"])
    args = ap.parse_args()

    print(f"LoRA rank sweep — base {args.base}")
    print(f"  targets: {', '.join(args.targets)}   alpha: {args.alpha} (fixed)\n")
    print(f"  {'rank':>4}  {'trainable':>12}  {'total':>13}  {'trainable %':>12}")
    print(f"  {'-'*4}  {'-'*12}  {'-'*13}  {'-'*12}")
    for r in args.ranks:
        trainable, total = trainable_counts(args.base, r, args.alpha, args.targets)
        pct = 100.0 * trainable / total
        print(f"  {r:>4}  {trainable:>12,}  {total:>13,}  {pct:>11.4f}%")
    print("\n  Read it: trainable grows LINEARLY with rank (double r, double the adapter),")
    print("  while total barely moves — the base is frozen. More rank = more capacity to")
    print("  fit, and more room to overfit a small set. r=8 is the lab's sweet spot here.")


if __name__ == "__main__":
    main()
