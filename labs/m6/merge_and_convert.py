# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "torch",
#   "transformers>=4.51",
#   "peft",
# ]
# ///
"""OpsMate merge + convert — bolt the fittings in, then ship a servable GGUF.

Two steps, one script:

  1. MERGE. peft's merge_and_unload() folds the LoRA adapter back into the base
     weights, producing a normal, standalone model with no adapter attached. This
     is the "leave the fittings in the building" choice: the merged model serves
     exactly like the base did (llama-server does not need to know LoRA exists),
     at the cost of no longer being able to unbolt the adapter. (The alternative —
     serving base + adapter separately — keeps the adapter swappable but needs a
     runtime that loads adapters at serve time. The lesson covers the tradeoff.)

  2. CONVERT. The merged HF model is converted to a q8_0 GGUF with llama.cpp's
     convert_hf_to_gguf.py, so the SAME llama-server that served the base GGUF in
     M3 can serve the tuned one with only a filename change. The spike measured
     this at ~14 s / ~767 MB. The output drops into labs/opsmate/models/gguf/ next
     to the base GGUF — which is exactly the v0-base / v1.0-tuned pair M7 will
     version and package.

llama.cpp is not a Python dependency you can pip-install for this — the converter
is a script inside the repo. This tool SHALLOW-CLONES llama.cpp on first run
(--depth 1, into labs/m6/.llama.cpp) and calls the converter from there. Nothing
is built; only the Python converter script is used.

Usage:
  uv run labs/m6/merge_and_convert.py
  uv run labs/m6/merge_and_convert.py --skip-convert     # merge only (fast smoke)
  uv run labs/m6/merge_and_convert.py --outtype q8_0

Flags:
  --base         base model dir     (default labs/opsmate/models/qwen3-0.6b)
  --adapter      adapter dir        (default labs/opsmate/train/adapter)
  --merged-dir   merged HF output   (default labs/opsmate/train/merged)
  --gguf-out     final GGUF path    (default labs/opsmate/models/gguf/opsmate-tuned-q8_0.gguf)
  --outtype      GGUF quant type    (default q8_0)
  --llama-dir    llama.cpp checkout (default labs/m6/.llama.cpp)
  --skip-convert merge only, skip the GGUF step (no llama.cpp needed)
"""
import os
import sys
import time
import shutil
import argparse
import subprocess

LLAMA_REPO = "https://github.com/ggml-org/llama.cpp"


def merge(base: str, adapter: str, merged_dir: str) -> None:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print(f"==> merge: {base}  +  {adapter}")
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float32)
    model = PeftModel.from_pretrained(model, adapter)
    # Fold the low-rank adapter into the base weights and drop the adapter wrappers.
    merged = model.merge_and_unload()
    os.makedirs(merged_dir, exist_ok=True)
    merged.save_pretrained(merged_dir)
    # The tokenizer travels with the model — the converter needs it beside the weights.
    AutoTokenizer.from_pretrained(adapter if os.path.isdir(adapter) else base).save_pretrained(merged_dir)
    print(f"    merged model saved to {merged_dir}  ({time.time() - t0:.1f}s)")


def ensure_llama(llama_dir: str) -> str:
    """Shallow-clone llama.cpp once and return the path to convert_hf_to_gguf.py."""
    converter = os.path.join(llama_dir, "convert_hf_to_gguf.py")
    if os.path.isfile(converter):
        return converter
    if shutil.which("git") is None:
        print("git not found — needed to fetch the llama.cpp converter", file=sys.stderr)
        sys.exit(1)
    print(f"==> cloning llama.cpp (shallow) into {llama_dir} ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", LLAMA_REPO, llama_dir],
        check=True,
    )
    if not os.path.isfile(converter):
        print(f"converter not found at {converter} after clone", file=sys.stderr)
        sys.exit(1)
    return converter


def convert(merged_dir: str, gguf_out: str, outtype: str, converter: str) -> None:
    os.makedirs(os.path.dirname(gguf_out), exist_ok=True)
    print(f"==> convert: {merged_dir}  ->  {gguf_out}  ({outtype})")
    t0 = time.time()
    # The converter itself needs a couple of packages (gguf, torch, transformers,
    # sentencepiece). We run it under `uv run --with ...` so no global install is
    # required — the same uv-first pattern the training step uses.
    cmd = [
        "uv", "run",
        "--with", "gguf", "--with", "torch",
        "--with", "transformers>=4.51", "--with", "sentencepiece", "--with", "protobuf",
        "python", converter,
        merged_dir,
        "--outfile", gguf_out,
        "--outtype", outtype,
    ]
    subprocess.run(cmd, check=True)
    size_mb = os.path.getsize(gguf_out) / (1024 * 1024)
    print(f"    wrote {gguf_out}  ({size_mb:.0f} MB, {time.time() - t0:.1f}s)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="labs/opsmate/models/qwen3-0.6b")
    ap.add_argument("--adapter", default="labs/opsmate/train/adapter")
    ap.add_argument("--merged-dir", default="labs/opsmate/train/merged")
    ap.add_argument("--gguf-out", default="labs/opsmate/models/gguf/opsmate-tuned-q8_0.gguf")
    ap.add_argument("--outtype", default="q8_0")
    ap.add_argument("--llama-dir", default="labs/m6/.llama.cpp")
    ap.add_argument("--skip-convert", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.adapter):
        print(f"no adapter at {args.adapter} — run train_lora.py first", file=sys.stderr)
        sys.exit(1)

    merge(args.base, args.adapter, args.merged_dir)

    if args.skip_convert:
        print("\n--skip-convert set: merged model ready, GGUF step skipped.")
        return

    converter = ensure_llama(args.llama_dir)
    convert(args.merged_dir, args.gguf_out, args.outtype, converter)

    print(f"\ndone — serve it by swapping the compose model file:")
    print(f"  MODEL_GGUF={os.path.basename(args.gguf_out)} make -C labs/opsmate up")


if __name__ == "__main__":
    main()
