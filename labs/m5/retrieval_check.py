# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "pyyaml"]
# ///
"""OpsMate retrieval-layer eval — the deterministic half of the golden set.

For every golden question whose `layer` is `retrieval` or `generation`, hit the
app's /retrieve and check that the question's `expect_source` runbook appears in
the top-k results. This asserts the RIGHT pages get put in front of the model —
phrase-independent, stable, and fast. It says nothing about the wording of the
generated answer (that is promptfoo's job, the graded generation layer).

Why a script and not promptfoo: "the correct source file is in the top-3" is a
check over a JSON list from a GET endpoint, which promptfoo's provider/transform
model can express only awkwardly. A tiny runner is clearer, and it is the exact
same check the X-Ray Evals lens reads back.

Usage:
  uv run labs/m5/retrieval_check.py
  uv run labs/m5/retrieval_check.py --k 3 --golden labs/opsmate/evals/golden.yaml

Env / flags:
  APP_URL      OpsMate app base URL      (default http://localhost:8001)
  --k          top-k to consider a hit   (default 3)
  --golden     path to golden.yaml       (default labs/opsmate/evals/golden.yaml)
  --out        JSON summary output path   (default labs/opsmate/evals/retrieval-latest.json)

Exit code is 0 when every retrieval check passes, 1 otherwise — so CI (M12) can
gate on it directly.
"""
import os
import sys
import json
import argparse
import datetime
import urllib.parse

import httpx
import yaml

APP_URL = os.environ.get("APP_URL", "http://localhost:8001")


def retrieve(question: str, k: int) -> list[dict]:
    url = f"{APP_URL}/retrieve?q={urllib.parse.quote(question)}&k={k}"
    resp = httpx.get(url, timeout=60.0)
    resp.raise_for_status()
    return resp.json().get("results", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--golden", default="labs/opsmate/evals/golden.yaml")
    ap.add_argument("--out", default="labs/opsmate/evals/retrieval-latest.json")
    args = ap.parse_args()

    with open(args.golden, "r", encoding="utf-8") as fh:
        golden = yaml.safe_load(fh)

    # Retrieval is checkable for any question that carries an expect_source —
    # that is every retrieval- and generation-layer question. Honesty questions
    # have no correct source (they are unanswerable), so they are skipped here.
    checkable = [
        q for q in golden["questions"]
        if q.get("expect_source") and q.get("layer") in ("retrieval", "generation")
    ]

    print(f"OpsMate retrieval-layer eval — {len(checkable)} questions, top-{args.k}")
    print(f"app: {APP_URL}\n")

    results = []
    passed = 0
    for q in checkable:
        want = q["expect_source"]
        try:
            hits = retrieve(q["question"], args.k)
        except Exception as exc:  # noqa: BLE001 — surface any transport error per-question
            print(f"  FAIL  {q['id']:<28} /retrieve error: {exc}")
            results.append({"id": q["id"], "layer": q["layer"], "expect_source": want,
                            "ok": False, "top_sources": [], "error": str(exc)})
            continue

        top_sources = [h.get("source") for h in hits]
        # Rank of the wanted source in the top-k, 1-based; None if absent.
        rank = next((i + 1 for i, s in enumerate(top_sources) if s == want), None)
        ok = rank is not None
        passed += int(ok)
        status = "PASS" if ok else "FAIL"
        where = f"rank {rank}" if ok else f"not in top-{args.k}"
        print(f"  {status}  {q['id']:<28} want {want:<26} ({where})")
        if not ok:
            print(f"         got: {top_sources}")
        results.append({"id": q["id"], "layer": q["layer"], "expect_source": want,
                        "ok": ok, "rank": rank, "top_sources": top_sources})

    total = len(checkable)
    pct = round(100.0 * passed / total, 1) if total else 0.0
    print(f"\nretrieval layer: {passed}/{total} passed ({pct}%)")

    summary = {
        "layer": "retrieval",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "app_url": APP_URL,
        "k": args.k,
        "golden": args.golden,
        "passed": passed,
        "total": total,
        "pct": pct,
        "results": results,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"wrote {args.out}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
