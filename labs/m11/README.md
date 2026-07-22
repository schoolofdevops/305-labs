# M11 lab assets — Autoscaling & GitOps: operating the platform

This module makes the OpsMate platform **operable**. The observed metric from M10
becomes a control signal (autoscale on queue depth), the model version becomes a
fact in git (promote via PR, roll back via `git revert`), and the training loop
becomes a governed pipeline step (an Argo Workflow under a CPU cap). The serving
and observability manifests live under `labs/opsmate/k8s/`; the training assets
and checks live here.

| Path | What it is |
| --- | --- |
| `labs/opsmate/k8s/kind-config.yaml` (grown) | Adds the base-model **extraMount** (`./models` → `/models`, read-only) so the in-cluster training pod can read the base weights off the node. `extraMounts` are read at cluster-create, so M11 recreates the cluster at module start. |
| `labs/opsmate/k8s/autoscale.yaml` (refined) | The KEDA **ScaledObject**: a prometheus trigger on `sum(llamacpp:requests_deferred)` (queue depth, not CPU%), threshold 2, min 1 / max 2. KEDA generates `keda-hpa-opsmate-model` from it. |
| `labs/opsmate/k8s/gitea.yaml` | The in-cluster **environment-repo host**: gitea (sqlite, install-lock, 256Mi) in namespace `git`, holding the `opsmate-env` repo Argo CD reconciles. |
| `labs/opsmate/k8s/argocd-values.yaml` | Slim **Argo CD** Helm values: dex + notifications disabled, ApplicationSet controller disabled with the **correct** key (`applicationSet.replicas: 0`, not the no-op `enabled: false`), and memory limits on the kept components. |
| `labs/m11/Dockerfile.train` | The **training image** (`opsmate-train:m11`): CPU-torch deps baked (not pip-at-pod-start — the spike's 14-min wall), the M6 `train_lora.py`, and a smoke dataset. `kind load`ed, run with `imagePullPolicy: Never`. |
| `labs/m11/train_lora.py` | The M6 trainer, copied so the image build context is self-contained. Same training contract across the course; already supports `--batch --max-len --max-steps`. |
| `labs/m11/smoke-train.jsonl` | An 8-sample smoke dataset in the trainer's schema (`messages[]` + `source`), baked into the image so the in-cluster job needs no data mount. |
| `labs/m11/train-workflow.yaml` | The fine-tune as an **Argo Workflow**: base model from the node mount, `imagePullPolicy: Never`, the 8 GB smoke profile (`--batch 1 --max-len 256 --max-steps 2`), and a **CPU limit** (the circuit breaker that keeps a training pod from starving the control plane). |
| `labs/m11/rbac-executor.yaml` | The executor **RBAC** (SA + Role + RoleBinding) granting `workflowtaskresults` create/patch — the fix for the phase-vs-containerStatuses trap (the phase reads Error while the main container exits 0). |
| `labs/m11/checks.json` | The lab's success end-state (12 checks). |
| `labs/m11/deep-dive.checks.json` | The Deep Dive's checks. |

## The three operating shifts

```
M10 observed the metric  ->  M11 lets the metric DRIVE the system

1. Autoscale on a real signal   queue depth (requests_deferred), not CPU%
   KEDA -> generated HPA -> 1..2 replicas.  A queued request burns ~0 CPU.

2. Model version in git          promote = PR (tag bump), rollback = git revert
   Argo CD reconciles opsmate-env onto the cluster. Change the paper, the
   building follows.

3. Training as a pipeline step    Argo Workflow, CPU-capped, serving drained first
   The cap protects the CONTROL PLANE, not just the pod (the starvation
   post-mortem). One heavyweight at a time.
```

## The two designed exhibits (both fixed through git)

The promotion story is where the lab teaches the sharpest lesson, via two
spike-proven exhibits:

- **Exhibit A — the presence-cache lie.** A naive tag bump merges, the pod rolls,
  and git claims the new version — but the initContainer's idempotency guard sees
  a GGUF already on the PVC and **skips the unpack**, so the server keeps serving
  the OLD bytes. The same presence-cache that makes scale-out fast makes naive
  promotion a lie. Fix: **per-tag unpack dirs** (`/model/kits/<tag>/...`) so a new
  tag is a new path the guard has never seen.
- **Exhibit B — the per-kit GGUF filename (an M9 echo).** The candidate kit ships
  its GGUF as `opsmate-tuned-q8_0.gguf`, not `qwen3-0.6b-q8_0.gguf`, so the server
  crash-loops on the old filename. Fix: point the guard and the server `-m` at the
  candidate's real filename.

Both fixes land **through git** (a commit in `opsmate-env`, reconciled by Argo) —
never `kubectl edit`, which the next sync would overwrite. Rollback is `git revert`
(the PR merge needs `-m 1`), and it is instant **because** the old bytes never left
the PVC — the symmetry with Exhibit A is the point.

## The training guardrail (the starvation post-mortem)

The spike proved an **uncapped** training pod drives node CPU to ~247% and starves
the kube-apiserver: TLS handshakes time out, `kubectl` stops working, `crictl stop`
returns DeadlineExceeded, and the break-glass is `pkill -9` on the node. The fix is
two guardrails the lab enforces:

1. `limits.cpu: "2"` on the training pod — the limit protects the control plane, a
   set of ordinary processes competing for the same CPU.
2. **One heavyweight at a time** — drain serving first via KEDA's `paused-replicas`
   annotation (double duty as the drain lever) + scaling observability to 0.

The Deep Dive walks the full post-mortem, the break-glass ladder, and KEDA's
external-metrics internals.

## Checks

- `checks.json` — the lab end-state: the base-model mount grew into kind-config,
  the cluster is up with the base weights on the node, autoscale scales on queue
  depth, KEDA generates the HPA, the Argo CD values are slim (with the correct
  ApplicationSet off-switch), gitea is the env-repo host, the training workflow is
  CPU-capped with the smoke profile, the executor RBAC grants
  `workflowtaskresults`, the training image builds + loads, the smoke dataset
  matches the trainer schema, and the lab teaches the git-only promotion arc. Heavy
  steps **self-seed** (`make k8s-up`, seed the kits, helm-install KEDA, apply the
  ScaledObject, build + load the training image). Every cluster check exports
  `KUBECONFIG=labs/opsmate/k8s/kubeconfig`; assertions are shape-true, not
  value-exact.
- `deep-dive.checks.json` — the Deep Dive page: the CPU cap is on the training
  pod, the executor RBAC exists, and the page documents the break-glass ladder,
  the external-metrics/paused-replicas internals, and the phase-vs-containerStatuses
  reading.

## Isolation & persistence (unchanged from M8–M10)

- **Isolated kubeconfig** at `labs/opsmate/k8s/kubeconfig` — every `kubectl` and
  `helm` carries `--kubeconfig` / exported `KUBECONFIG`; the default context is
  never touched.
- **Registry data persists** on `labs/opsmate/data/zot`; teardown deletes the
  cluster only. The Helm releases (KEDA, Argo CD, gitea, Argo Workflows) die with
  the cluster; the manifests stay in `labs/`.
- **One heavyweight stack at a time**: the autoscale cycle runs with serving up;
  the training workflow runs only **after** serving is drained (KEDA
  `paused-replicas: "0"` + observability scaled to 0). Full-fidelity training is
  the 16 GB / host path (M6), not this shared-node job.
