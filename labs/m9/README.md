# M9 lab assets — Serving patterns: the canary, the quality gate, the frontier

This module grows the M8 serving deployment into a **two-version fleet behind a
router** and canaries a model version on QUALITY grounds. The runnable pieces
live under `labs/opsmate/k8s/canary/` (the manifests this module adds) and here
(the quality gate + checks).

| Path | What it is |
| --- | --- |
| `labs/opsmate/k8s/canary/canary-server.yaml` | The **canary backend** (`opsmate-canary` Deployment + Service): an M8-shaped model server whose initContainer pulls `opsmate/model:1.0.0-candidate` (the M6 loser). Its `-m` arg is DELIBERATELY the base filename — the designed model-load crash the lab fixes in Step 2. |
| `labs/opsmate/k8s/canary/router.yaml` | The **router**: an nginx `split_clients` ConfigMap (90/10 base/canary), the `X-Served-By` response header (the per-request observability hook), and a 64Mi nginx Deployment + Service. Clients now dial the router. |
| `labs/opsmate/k8s/canary/promote-staged.yaml` | The **staged-promotion runbook** — the weight ladder (0 → 10 → 50 → 100), documented as copy-in `split_clients` blocks. No new object; promotion is a ConfigMap edit + `rollout restart`. |
| `labs/opsmate/k8s/DECISION-TREE.md` | The **serving decision tree** (Deployment vs router+canary vs KServe vs llm-d) — the one-page capstone artifact, referenced again in M13. |
| `labs/m9/canary_gate.py` | The **quality gate**: runs the golden generation questions against the canary and base Services directly, scores with the golden set's own wide nets, and prints **PROMOTE** or **ROLLBACK** (exit 0 / 1). The readiness probe cannot taste the food; this can. |

## The chain the lab runs (all live, 8 GB core)

```
M7 registry @ localhost:5100    (base 1.0.0 signed + 1.0.0-candidate, the M6 loser)
   │
   ▼
slim KIND cluster 'opsmate'     (make k8s-up — isolated kubeconfig, M8 habit)
   │  apply model-server.yaml (base, M8)  +  apply canary/canary-server.yaml
   ▼
opsmate-model  1/1  (base 1.0.0)      opsmate-canary  1/1  (1.0.0-candidate)
        └──────────────┬───────────────────────┘
                       ▼
           opsmate-router (nginx split_clients 90/10, X-Served-By)
                       │  clients dial the router; ~92/8 over 100 requests
                       ▼
        canary_gate.py  → golden set vs BOTH backends  → ROLLBACK (candidate lost)
                       │  weight → 0, rollout restart → 100/0
                       ▼
        staged-promote drill (10 → 50 → 100) with the base as stand-in
```

## Reading the split honestly

The lab drives the split at **n=20 first (the illusion — you may see 0 canary
hits: 0.9²⁰ ≈ 12% of the time you get none)**, then at **n=100 (the ~92/8 shape
the weights predict)**. Judging a 10% canary from 20 requests is judging a coin
from three flips. The `X-Served-By` header is what you count; n=100 is the
discipline.

## The quality gate is the point

The canary pod is `1/1 Running` and answers every request — and it is the wrong
model. `canary_gate.py` hits both backends directly with the golden generation
questions and compares pass-counts. The candidate is the M6 tune that already
lost the baseline (no-RAG generation regressed), so the gate prints **ROLLBACK**,
and you act on it: weight → 0, `rollout restart`, verify 100/0. Promotion and
rollback are DATA verbs, not crash verbs.

## Checks

- `checks.json` — the lab's success end-state: cluster up + base and canary pods
  `1/1 Running` from their kits, the router split reaching both backends
  (`X-Served-By` present for both over enough requests), a completion driven
  through the router, the quality gate printing a verdict, the ConfigMap carrying
  the split, and the decision-tree artifact present. Heavy steps self-seed
  (`make k8s-up` + seed the kits + apply base/canary/router); every check exports
  `KUBECONFIG=labs/opsmate/k8s/kubeconfig`. Assertions are shape-true, not
  value-exact (the split is probabilistic).
- `deep-dive.checks.json` — the Deep Dive page: the KServe `InferenceService`
  shape reads (schema present via `kubectl explain`-style checks where the CRD is
  installed, else the manifest is well-formed), the `split_clients` weight math,
  and the decision-tree branches present.

## Isolation & persistence (unchanged from M8)

- **Isolated kubeconfig** at `labs/opsmate/k8s/kubeconfig` — every `kubectl`
  carries `--kubeconfig`; the default context is never touched.
- **Registry data persists** on `labs/opsmate/data/zot`; teardown deletes the
  cluster only. `DECISION-TREE.md` stays (capstone artifact).
- **One stack at a time**: the Compose model service is DOWN; only `registry`
  runs alongside KIND.
