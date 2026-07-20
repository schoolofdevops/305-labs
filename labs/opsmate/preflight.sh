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
# The containers run wherever Docker runs. On macOS/Windows that is a fixed-size
# VM whose memory is already carved out of the host — so when Docker answers, we
# measure INSIDE the VM (that is the truth for container capacity), and only
# fall back to host-side gauges when Docker itself is not up yet.
free_mb() {
  if command -v docker >/dev/null 2>&1; then
    local vm_avail
    vm_avail="$(docker run --rm alpine sh -c "free -m" 2>/dev/null \
      | awk '/^Mem:/ {print $7}')"
    if [ -n "${vm_avail:-}" ] && [ "$vm_avail" -gt 0 ] 2>/dev/null; then
      echo "$vm_avail"
      return
    fi
  fi
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

# --- optional signature verification (M7) ----------------------------------
# When VERIFY_SIGNATURE=1, refuse to start unless the model artifact you are about
# to serve has a valid Cosign signature in the local registry. This is the
# verify-before-deploy gate in miniature — the same check M8's Kubernetes admission
# controller will enforce on the cluster. Unset (the default) it is skipped
# silently, so earlier modules and CI are unaffected. Verification is by DIGEST:
# a signature is bound to exact bytes, so we resolve the tag to its digest first.
if [ "${VERIFY_SIGNATURE:-0}" = "1" ]; then
  VERIFY_TAG="${VERIFY_TAG:-1.0.0}"
  VERIFY_REPO="${VERIFY_REPO:-localhost:5100/opsmate/model}"
  PUB="$(cd "$(dirname "$0")" && pwd)/signing/cosign.pub"
  echo "==> Signature gate: verifying ${VERIFY_REPO}:${VERIFY_TAG} before serving"
  if [ ! -f "$PUB" ]; then
    echo "    ✗ No public key at $PUB — generate keys first (Lab Step 6):"
    echo "      cd signing && cosign generate-key-pair"
    exit 1
  fi
  # Resolve the tag to its manifest digest (a signature is bound to bytes, not tags).
  # VERIFY_REPO is host/repo (e.g. localhost:5100/opsmate/model); split on the first /.
  REG_HOST="${VERIFY_REPO%%/*}"
  REG_PATH="${VERIFY_REPO#*/}"
  DIGEST="$(curl -sI -H 'Accept: application/vnd.oci.image.manifest.v1+json' \
    "http://${REG_HOST}/v2/${REG_PATH}/manifests/${VERIFY_TAG}" \
    | awk 'tolower($1)=="docker-content-digest:"{print $2}' | tr -d '\r')"
  if [ -z "$DIGEST" ]; then
    echo "    ✗ Could not resolve ${VERIFY_REPO}:${VERIFY_TAG} to a digest."
    echo "      Is the registry up (make up) and the kit pushed (Lab Step 3)?"
    exit 1
  fi
  if cosign verify --key "$PUB" --allow-insecure-registry --insecure-ignore-tlog \
       "${VERIFY_REPO}@${DIGEST}" >/dev/null 2>&1; then
    echo "    ✓ Signature valid for ${VERIFY_REPO}@${DIGEST%%:*}:… — cleared to serve."
  else
    echo "    ✗ NO valid signature for ${VERIFY_REPO}:${VERIFY_TAG} (digest ${DIGEST})."
    echo "      Refusing to serve an unsigned/unverified model. This is the gate:"
    echo "      an unsigned candidate (e.g. 1.0.0-candidate) fails here by design."
    echo "      Sign it (Lab Step 6) or serve the signed tag (VERIFY_TAG=1.0.0)."
    exit 1
  fi
fi

echo "    Preflight passed."
