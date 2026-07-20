#!/usr/bin/env bash
# ============================================================================
# M7 checks seed — idempotently reach the lab's success end-state so the machine
# checks can run from a clean tree. Safe to re-run: every step is a no-op if the
# artifact already exists. Called by labs/m7/checks.json (and handy by hand).
#
#   registry up  ->  pack+push base (1.0.0) + candidate (1.0.0-candidate)
#                ->  pack+push adapter (1.0.0)  ->  cosign key + sign base by digest
#
# Requires: docker, kit, cosign, curl, jq. Run from the labs repo root.
# ============================================================================
set -uo pipefail

REG=localhost:5100
OPSMATE=labs/opsmate
COMPOSE="$(docker compose version >/dev/null 2>&1 && echo 'docker compose' || echo 'docker-compose')"

log() { echo "[seed] $*"; }

# --- registry up ------------------------------------------------------------
mkdir -p "$OPSMATE/data/zot"
if ! curl -fsS "http://$REG/v2/_catalog" >/dev/null 2>&1; then
  log "starting registry service"
  $COMPOSE -f "$OPSMATE/compose.yaml" up -d registry >/dev/null 2>&1
  for _ in $(seq 1 20); do
    curl -fsS "http://$REG/v2/_catalog" >/dev/null 2>&1 && break
    sleep 1
  done
fi
curl -fsS "http://$REG/v2/_catalog" >/dev/null 2>&1 || { log "registry not reachable"; exit 1; }

# --- base 1.0.0 -------------------------------------------------------------
if ! curl -fsS "http://$REG/v2/opsmate/model/tags/list" 2>/dev/null | grep -q '"1.0.0"'; then
  log "packing + pushing base 1.0.0"
  kit pack "$OPSMATE" -t "$REG/opsmate/model:1.0.0" >/dev/null 2>&1
  kit push "$REG/opsmate/model:1.0.0" --plain-http >/dev/null 2>&1
fi

# --- candidate 1.0.0-candidate (tuned GGUF, edited Kitfile via a temp copy) --
if ! curl -fsS "http://$REG/v2/opsmate/model/tags/list" 2>/dev/null | grep -q '"1.0.0-candidate"'; then
  if [ -f "$OPSMATE/models/gguf/opsmate-tuned-q8_0.gguf" ]; then
    log "packing + pushing candidate 1.0.0-candidate"
    TMPKIT="$(mktemp)"
    sed -e 's#path: models/gguf/qwen3-0.6b-q8_0.gguf#path: models/gguf/opsmate-tuned-q8_0.gguf#' \
        -e 's#name: opsmate-base#name: opsmate-tuned#' \
        "$OPSMATE/Kitfile" > "$TMPKIT"
    kit pack "$OPSMATE" -f "$TMPKIT" -t "$REG/opsmate/model:1.0.0-candidate" >/dev/null 2>&1
    kit push "$REG/opsmate/model:1.0.0-candidate" --plain-http >/dev/null 2>&1
    rm -f "$TMPKIT"
  else
    log "tuned GGUF absent — skipping candidate (M6 not completed); base still covers most checks"
  fi
fi

# --- adapter 1.0.0 ----------------------------------------------------------
if ! curl -fsS "http://$REG/v2/opsmate/adapter/tags/list" 2>/dev/null | grep -q '"1.0.0"'; then
  if [ -f "$OPSMATE/train/adapter/adapter_model.safetensors" ]; then
    log "packing + pushing adapter 1.0.0"
    kit pack "$OPSMATE" -f Kitfile.adapter -t "$REG/opsmate/adapter:1.0.0" >/dev/null 2>&1
    kit push "$REG/opsmate/adapter:1.0.0" --plain-http >/dev/null 2>&1
  else
    log "adapter absent — skipping adapter kit (M6 not completed)"
  fi
fi

# --- cosign keys + sign base by digest --------------------------------------
mkdir -p "$OPSMATE/signing"
if [ ! -f "$OPSMATE/signing/cosign.key" ]; then
  log "generating cosign key pair"
  ( cd "$OPSMATE/signing" && COSIGN_PASSWORD="" cosign generate-key-pair >/dev/null 2>&1 )
fi

BASE_DIGEST="$(curl -sI -H 'Accept: application/vnd.oci.image.manifest.v1+json' \
  "http://$REG/v2/opsmate/model/manifests/1.0.0" \
  | awk 'tolower($1)=="docker-content-digest:"{print $2}' | tr -d '\r')"
if [ -n "$BASE_DIGEST" ]; then
  # sign only if not already signed (verify is the cheap idempotency probe)
  if ! cosign verify --key "$OPSMATE/signing/cosign.pub" --allow-insecure-registry \
        --insecure-ignore-tlog "$REG/opsmate/model@$BASE_DIGEST" >/dev/null 2>&1; then
    log "signing base 1.0.0 by digest"
    COSIGN_PASSWORD="" cosign sign --key "$OPSMATE/signing/cosign.key" \
      --allow-insecure-registry --use-signing-config=false --tlog-upload=false --yes \
      "$REG/opsmate/model@$BASE_DIGEST" >/dev/null 2>&1
  fi
fi

log "seed complete"
