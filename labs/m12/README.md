# labs/m12 — Gateway, Evals & Guardrails (OpsMate v3.0)

Assets for **Module 12 · Trust**. This is the **Compose phase** (the KIND cluster
is down; one heavyweight set at a time). The gateway stack lives in
`labs/opsmate/gateway/`; this directory holds the red-team script and the eval
gate. No `KUBECONFIG` is needed — nothing here talks to a cluster.

## What's here

| Path | What it is |
| --- | --- |
| `red-team.sh` | Scripted attack set run through the **guarded gateway path** — a direct injection, the **M4 corpus payload** (`deploy-rollback.md` "Operator note", verbatim), a **rephrased version of that same hijack** with the tell-tale attack phrasings stripped, and a PII probe. Emits a BLOCKED/THROUGH ledger. The finding: the injection heuristic is a **template matcher** — it blocks the M4 payload on its known-attack phrasings, but the semantically identical rephrase sails THROUGH (the false negative). Real defense governs what enters the prompt, not one string matcher at the door. |
| `eval-gate/promptfooconfig.gate.yaml` | The golden-set eval pointed at the **gateway** `/v1` (virtual-key auth) instead of the app. Runs the **must-pass subset** (`gate-tests.yaml` — the `gate_must_pass` questions on deterministic lexical nets), because through the gateway there is no retrieval and the `pre_call` mask over-fires, so the full set can't gate a healthy model. Gate contract: promptfoo exits `0` all-green, `100` on any fail. Use `--no-cache` so re-runs actually re-drive the model. |
| `eval-gate/gate.yaml` | The eval gate as an **Argo Workflows** step, extending the M11 pipeline: a two-step sequence where `promote` runs only `when` the `eval-gate` step passed. Reuses the M11 `argo-workflow` executor SA. |
| `eval-gate/gate-workflow.yml` | The eval gate as a **GitHub Actions** workflow, gating the promotion PR (triggers on `manifests/model-server.yaml`). Blocks the merge on a red eval. Grown from the M5 `ci-preview.yml` stub. |
| `checks.json` | Machine-readable assertions for the core lab (config refinements + assets present + arc taught). |
| `deep-dive.checks.json` | Assertions for the Deep Dive (cost-accounting path, hook ordering, gate wiring documented). |

## How the pieces connect

```
golden.yaml (M5, versioned; gate_must_pass flags the stable subset)
   → make_promptfoo_tests.py  (single source of truth → generation-tests.yaml + gate-tests.yaml)
       → promptfooconfig.gate.yaml  (run gate-tests.yaml vs the gateway /v1, virtual key, --no-cache)
           → exit code 0 / 100
               → gate-workflow.yml   (GitHub Actions required check → merge gate)
               → gate.yaml           (Argo step → promote when PASS)
```

## Running the assets (gateway up, from the labs repo root)

```bash
# 1. gateway up (see the lab Step 1) + a virtual key minted (Step 3)
# 2. red-team the guarded path:
GW=http://localhost:4000 KEY=sk-... bash labs/m12/red-team.sh

# 3. eval gate as a local dry-run (the same command a CI runner executes):
uv run labs/m5/make_promptfoo_tests.py   # also writes gate-tests.yaml (the must-pass subset)
GATEWAY_URL=http://localhost:4000 GATEWAY_KEY=sk-eval-runner \
  npx -y promptfoo@latest eval -c labs/m12/eval-gate/promptfooconfig.gate.yaml \
  -o labs/m12/eval-gate/gate-latest.json --max-concurrency 2 --no-cache ; echo "exit=$?"
```

## Scope notes (8 GB path)

- **The gate scores a must-pass subset, and that is the honest lesson.** Routed
  through the gateway there is (a) no retrieval — the model answers without the
  RAG app's runbook context, scoring like the M5 no-RAG baseline — and (b) the
  `pre_call` PII mask over-fires on eval content. So the gate keys on the
  `gate_must_pass` questions (answerable from the model alone, no maskable PII)
  on deterministic lexical nets: green on a healthy model, red on a regression.
  Full-fidelity gating (RAG app in front for retrieval, eval path exempt from
  masking) is the **16 GB / cluster** path; the exit-code contract is identical.
- The eval gate is authored as real CI (Actions + Argo) but **run** here as a
  local dry-run against the Compose-phase gateway. A full **in-cluster replay**
  (gateway deployed inside the cluster, Argo workflow submitted against it) is
  the **16 GB / cluster** path — the wiring is identical, only co-residency
  differs.
- `ragas` (industrial RAG metrics) is **surveyed, not installed** — the judge
  stays the M5 two-layer pattern (contains-any nets + a local 0.6B judge) that
  already runs on this box. See the Deep Dive.
