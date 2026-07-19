#!/usr/bin/env bash
# ============================================================================
# OpsMate preflight — refuse to start the stack when the box cannot hold it.
#
# The stack grows across the course; every module its memory floor rises. This
# script reads FREE memory (not total) and stops early with a clear message
# rather than letting the container get OOM-killed mid-lab. Portable across
# macOS (vm_stat) and Linux (/proc/meminfo or free).
#
# Usage:  bash preflight.sh [REQUIRED_FREE_MB]
#   REQUIRED_FREE_MB defaults to the M3 floor. Later modules raise it.
# ============================================================================
set -euo pipefail

REQUIRED_MB="${1:-2200}"   # M3 floor: llama-server ~1.5 GiB under a 2 GiB cap + headroom
# M6: the served GGUF is switchable (MODEL_GGUF). Check whichever file will actually
# be served — so serving the tuned model with a missing/partial GGUF fails here, not
# in a container crash loop. Defaults to the base model when MODEL_GGUF is unset.
MODEL_FILE="$(cd "$(dirname "$0")" && pwd)/models/gguf/${MODEL_GGUF:-qwen3-0.6b-q8_0.gguf}"

# --- free memory, in MB, cross-platform ------------------------------------
free_mb() {
  if command -v vm_stat >/dev/null 2>&1; then
    # macOS: page size × (free + inactive + speculative) pages
    local page_size free_pages
    page_size="$(vm_stat | awk '/page size of/ {print $8}')"
    [ -z "${page_size:-}" ] && page_size=4096
    free_pages="$(vm_stat | awk '
      /Pages free/        {gsub("\\.","",$3); f=$3}
      /Pages inactive/    {gsub("\\.","",$3); i=$3}
      /Pages speculative/ {gsub("\\.","",$3); s=$3}
      END {print f+i+s}')"
    echo $(( free_pages * page_size / 1024 / 1024 ))
  elif [ -r /proc/meminfo ]; then
    # Linux: MemAvailable is the honest "usable without swapping" figure
    awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo
  elif command -v free >/dev/null 2>&1; then
    free -m | awk '/^Mem:/ {print $7}'
  else
    echo "-1"   # unknown platform — signal "cannot measure"
  fi
}

echo "==> OpsMate preflight"

# --- model file present and non-truncated ----------------------------------
if [ ! -f "$MODEL_FILE" ]; then
  echo "    ✗ Model file missing: $MODEL_FILE"
  echo "      Download it (Lab Step 1): the Qwen3-0.6B Q8_0 GGUF (~610 MB)."
  exit 1
fi
# GGUF files begin with the ASCII magic 'GGUF'. A partial download fails this.
MAGIC="$(head -c 4 "$MODEL_FILE" 2>/dev/null || true)"
if [ "$MAGIC" != "GGUF" ]; then
  echo "    ✗ Model file does not start with the GGUF magic — likely a partial download."
  echo "      Delete $MODEL_FILE and re-download it (Lab Step 1)."
  exit 1
fi
echo "    ✓ Model file present and looks like a real GGUF."

# --- free memory check -----------------------------------------------------
FREE="$(free_mb)"
if [ "$FREE" = "-1" ]; then
  echo "    ! Could not measure free memory on this OS — skipping the check."
  echo "      Make sure at least ${REQUIRED_MB} MB is free before you continue."
elif [ "$FREE" -lt "$REQUIRED_MB" ]; then
  echo "    ✗ Only ${FREE} MB free; the stack needs about ${REQUIRED_MB} MB."
  echo "      Close other apps (browsers and other containers are the usual culprits)"
  echo "      and re-run. Refusing to start rather than risk an OOM kill mid-lab."
  exit 1
else
  echo "    ✓ ${FREE} MB free (need ~${REQUIRED_MB} MB)."
fi

echo "    Preflight passed."
