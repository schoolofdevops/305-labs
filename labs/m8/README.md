# M8 lab assets — Serve OpsMate on Kubernetes

This module moves OpsMate off Compose and onto a slim KIND cluster. The runnable
pieces live under `labs/opsmate/` (the spine) and `labs/opsmate/k8s/` (the manifests
this module adds); this folder holds the capacity worksheet and the checks.

| Path | What it is |
| --- | --- |
| `labs/opsmate/k8s/kind-config.yaml` | Slim single-node KIND profile (name `opsmate`) with the containerd mirror mapping `localhost:5100` → host Zot for **image** pulls. Committed in the spike; the lab walks through it. |
| `labs/opsmate/k8s/model-server.yaml` | The serving Deployment (arm64 / 8 GB path): **PVC** + **initContainer** (pulls the signed M7 kit, `kit unpack --filter=model`) + **llama-server** container (probes + limits from the worksheet) + **ClusterIP Service**. The `hostAliases` block is the two-paths fix — its IP is host-specific. |
| `labs/opsmate/k8s/model-server-vllm.yaml` | The vLLM variant — same shape, differs only in image/args/port. Taught line-by-line; validated on x86 / 16 GB+ / cloud + recorded demo (arm64 8 GB crashes on inference, per M3). |
| `labs/opsmate/k8s/bad-liveness.yaml` | The deliberately-wrong probe patch for the Step 6 restart-loop exhibit (no startupProbe + aggressive liveness → CrashLoopBackOff). Never for production. |
| `labs/opsmate/Makefile` | `make k8s-up` (free-mem preflight → registry-up → kind create with isolated kubeconfig → node-Ready wait) / `make k8s-down` (kind delete; registry data persists). Compose verbs unchanged. |
| `labs/m8/capacity-worksheet.md` | The three-term capacity sum (weights + runtime + KV) the lab drives in Step 2. The memory limit is DERIVED here before it is written into the manifest. |

## The chain the lab runs (all live)

```
M7 registry @ localhost:5100        (the model source — signed opsmate/model:1.0.0)
   │  (containerd mirror covers IMAGE pulls; the initContainer HTTP needs hostAliases)
   ▼
slim KIND cluster 'opsmate'         (make k8s-up — isolated kubeconfig k8s/kubeconfig)
   │  kubectl apply -f k8s/model-server.yaml
   ▼
PVC  ← initContainer (kit unpack --filter=model)   ← the advance man, the artifact chain
   │
   ▼
llama-server pod  1/1 Running (~43s)   → ClusterIP Service opsmate-model:8080
   │  port-forward → the SAME M3 client → completion (client unchanged)
   ▼
X-Ray Kubernetes lens (kubectl proxy)  → pods/restarts + /metrics through the proxy
```

## Isolation & persistence

- **Isolated kubeconfig** at `labs/opsmate/k8s/kubeconfig` (gitignored — root `.gitignore`).
  Every `kubectl` command carries `--kubeconfig`; the default context is never touched.
- **Registry data persists** on `labs/opsmate/data/zot` across `make k8s-down` — the signed
  kits survive, so M9 re-creates the cluster (~30 s) and pulls the same `1.0.0`.
- **One stack at a time**: the Compose model service is DOWN throughout the KIND phase;
  only the `registry` compose service runs alongside (it is the model source).

## Checks

- `checks.json` — the lab's success end-state: Compose model down, cluster up (node Ready),
  M7 kits present, the manifest well-formed (PVC + initContainer artifact chain + probes),
  the model pod `1/1 Running` from the signed kit, a completion served through the Service,
  the worksheet filled, the bad-liveness exhibit present. Heavy steps self-seed
  (`make k8s-up` + `kubectl apply`); every check command exports
  `KUBECONFIG=labs/opsmate/k8s/kubeconfig`. Assertions are shape-true, not value-exact.
- `deep-dive.checks.json` — the Deep Dive page: the startupProbe budget reads off the live
  pod, /health stays green while requests_deferred moves (the backpressure disconnect),
  and the PriorityClasses register with the right values.
