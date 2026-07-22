#!/usr/bin/env bash
# ============================================================================
# OpsMate eval GATE — the promotion brake, as one thin script (M12).
#
# WHY THIS EXISTS AND WHY IT IS A SCRIPT, NOT RAW promptfoo.
# Raw `promptfoo eval` exits 100 whenever ANY assertion fails — so even a
# HEALTHY model (which never scores 15/15 on a wide golden set graded by a 0.6B
# judge) is "red" by that contract. That is not a gate; that is a flake. A real
# gate keys on a THRESHOLD: does the candidate hold the committed baseline floor?
# This mirrors M9's canary_gate.py (the same course pattern), promoted to CI.
#
# WHAT IT MEASURES.
# The generation-layer golden set (the questions with a `contains_any` net),
# scored DETERMINISTICALLY — the answer names the right thing, in any of several
# wordings — against the OpsMate ASSISTANT's /ask endpoint (retrieval in the
# path: the app retrieves the runbook, builds the prompt, and answers). This is
# "gate what you ship": v3.0 is the assistant behind the door, so the gate evals
# the assistant, not the bare model. No 0.6B judge in the gate — the judge is a
# smoke detector (M5), too noisy to threshold on; the deterministic net is the
# stable signal (healthy RAG lands ~11/12 run to run; break retrieval and it
# collapses to the no-RAG floor ~6/12).
#
# THE CONTRACT (what CI keys on):
#   generation pass count >= FLOOR  -> exit 0  (PROMOTE — quality held)
#   generation pass count <  FLOOR  -> exit 1  (BLOCK   — a regression shipped)
# FLOOR is the committed baseline yardstick (labs/opsmate/evals/baseline.md).
#
# Usage (from the labs repo root, the app up with retrieval in the path):
#   APP_URL=http://localhost:8001 FLOOR=8 bash labs/m12/eval-gate/gate.sh
# ============================================================================
set -uo pipefail

APP_URL="${APP_URL:-http://localhost:8001}"
GOLDEN="${GOLDEN:-labs/opsmate/evals/golden.yaml}"
# The committed baseline floor. baseline.md records the healthy RAG generation
# arm; retrieval intact lands ~11/12 deterministically, a broken/absent-retrieval
# regression collapses to the ~6/12 no-RAG level. 8 sits cleanly between them:
# it passes a healthy assistant and blocks one that has lost its grounding.
FLOOR="${FLOOR:-8}"

if [ "${TARGET:-rag}" = "norag" ]; then
  echo "OpsMate eval gate — generation golden set vs the BARE MODEL (no retrieval — the M5 control)"
else
  echo "OpsMate eval gate — generation golden set vs the ASSISTANT (${APP_URL}/ask, retrieval in the path)"
fi
echo "floor: >= ${FLOOR} (committed baseline: labs/opsmate/evals/baseline.md)"
echo "----------------------------------------------------------------------"

# Score the generation layer deterministically. python does the golden-set walk;
# it prints one PASS/fail line per question and a final "SCORE n/total".
#
# TARGET selects what is under test:
#   rag   (default) — the assistant's /ask (retrieval in the path). The real gate.
#   norag           — the bare model /v1 direct, NO retrieval (the M5 control arm).
#                     The lab uses this to prove the gate BITES: strip retrieval and
#                     the score collapses below the floor, exactly as a broken
#                     ingest or an un-grounded deploy would in production.
SCORE_LINE=$(GOLDEN="$GOLDEN" APP_URL="$APP_URL" TARGET="${TARGET:-rag}" \
  NORAG_URL="${NORAG_URL:-http://127.0.0.1:11434}" NORAG_MODEL="${NORAG_MODEL:-qwen3:0.6b}" \
  uv run --with httpx --with pyyaml python - <<'PY'
import os, yaml, httpx, sys
golden = yaml.safe_load(open(os.environ["GOLDEN"]))
target = os.environ.get("TARGET", "rag")
app = os.environ["APP_URL"].rstrip("/")
norag_url = os.environ["NORAG_URL"].rstrip("/")
norag_model = os.environ["NORAG_MODEL"]
gen = [q for q in golden["questions"] if q.get("layer") == "generation"]
passed = 0
for q in gen:
    try:
        if target == "norag":
            r = httpx.post(f"{norag_url}/v1/chat/completions",
                           json={"model": norag_model,
                                 "messages": [{"role": "user", "content": q["question"]}],
                                 "temperature": 0.0, "max_tokens": 1024}, timeout=180)
            ans = r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else ""
        else:
            r = httpx.get(f"{app}/ask", params={"q": q["question"]}, timeout=180)
            ans = r.json().get("answer", "") if r.status_code == 200 else ""
    except Exception as exc:                       # surface transport errors per-question
        print(f"  ERROR {q['id']}: {exc}", file=sys.stderr); ans = ""
    low = ans.lower()
    ok = any(s.lower() in low for s in q.get("contains_any", []))
    passed += int(ok)
    print(f"  {'PASS' if ok else 'fail'}  {q['id']}", file=sys.stderr)
print(f"{passed}/{len(gen)}")                       # the ONLY line on stdout: the score
PY
)

# The python block wrote the per-question ledger to stderr (shown live above) and
# the bare score to stdout (captured here). Parse "passed/total".
PASS="${SCORE_LINE%%/*}"
TOTAL="${SCORE_LINE##*/}"
echo "----------------------------------------------------------------------"
echo "generation passed: ${PASS}/${TOTAL}   (floor ${FLOOR})"

if [ "${PASS:-0}" -ge "$FLOOR" ]; then
  echo "VERDICT: PROMOTE — ${PASS} >= ${FLOOR}; the assistant holds the baseline."
  exit 0
else
  echo "VERDICT: BLOCK — ${PASS} < ${FLOOR}; quality regressed, promotion refused."
  exit 1
fi
