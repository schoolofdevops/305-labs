# M10 lab assets — Observability: metrics, traces & the cost of tokens

This module makes the OpsMate platform **visible**. The app joins the cluster
(M4 FastAPI, now OTel-instrumented), a Prometheus/Grafana pair scrapes and
renders the model server's LLM signals, and Phoenix collects the app's traces so
you can read the `ask -> retrieve -> generate` waterfall of a single request. The
manifests live under `labs/opsmate/k8s/`; the runnable extras and checks live
here.

| Path | What it is |
| --- | --- |
| `labs/opsmate/app/main.py` (edited) | The M4 app, now **OTel-instrumented**. Env-gated on `OTEL_EXPORTER_OTLP_ENDPOINT`: inert in Compose/CI, live on the cluster. Manual spans wrap the pipeline — `ask` (CHAIN) → `retrieve` (RETRIEVER) + `generate` (LLM) — with OpenInference attributes including `llm.token_count.*` lifted from the model's usage block, and `input.value` (the prompt text — the log-hygiene beat). |
| `labs/opsmate/app/requirements.txt` (grown) | Adds the OTel deps (SDK, OTLP gRPC exporter, FastAPI instrumentation), majors pinned. |
| `labs/opsmate/k8s/app.yaml` | The **app on the cluster**: Deployment + Service, `MODEL_URL=http://opsmate-model:8080`, host-Ollama embeddings via the M8 `hostAliases` pattern, `OTEL_EXPORTER_OTLP_ENDPOINT=http://phoenix:4317`, the corpus as a ConfigMap, and an in-cluster **ingest Job** that POSTs `/ingest`. |
| `labs/opsmate/k8s/observability.yaml` | **Prometheus** (ConfigMap 5s scrape of `opsmate-model:8080`, 256Mi, 2h retention) + **Grafana** (provisioned datasource + one dashboard JSON: the LLM-signals wall) + **Phoenix** (OTLP collector + UI). Phoenix ships the **designed `PHOENIX_PORT` crash exhibit** — see below. |
| `labs/m3/loadtest.py` (reused) | The M3 bounded, laptop-safe load test. M10 reuses it as-is to drive the dashboard wall and watch `requests_deferred` climb while decode tok/s holds. |
| `labs/m10/checks.json` | The lab's success end-state (10 checks). |
| `labs/m10/deep-dive.checks.json` | The Deep Dive's checks (5 checks). |

## The two surfaces (metrics vs traces)

Observability for an LLM service has two halves, and they answer different
questions:

```
Prometheus + Grafana  =  the ward chart   (vitals over time, all patients)
     └─ "is the platform slow, and in which phase?"  decode tok/s, deferred queue

Phoenix (traces)      =  the case file    (one request, every step)
     └─ "where did THIS request spend its time, and what did it cost?"
        ask -> retrieve -> generate waterfall + per-request token counts
```

The Grafana dashboard reads the **M3 llamacpp families** cluster-scraped
(`predicted_tokens_seconds`, `prompt_tokens_seconds`, `requests_processing`,
`requests_deferred`, `prompt_tokens_total`, `tokens_predicted_total`) — the M1
metric model as a live wall. Phoenix reads the **app's OTel spans** — the same
pipeline you built in M4, now traced.

## The designed crash exhibit — Phoenix and service-link envs

`observability.yaml` ships the Phoenix Deployment **without** the `PHOENIX_PORT`
env, on purpose. Because there is a Service named `phoenix`, Kubernetes injects
a service-link env `PHOENIX_PORT=tcp://<ip>:6006` into the pod; Phoenix reads
`PHOENIX_PORT` as its own listen-port config, gets a `tcp://…` string where it
wants an integer, and crashes at startup with a log line that names the fix. The
lab applies it as shipped, reads the crash log, and adds the one-line env fix
(marked `# FIX:` in the manifest). This is the **third designed crash of the KIND
phase** — M8's `hostAliases` IP, M9's kit filename, M10's service-link env. The
pattern is the pedagogy: a real, reproducible failure that teaches a real
mechanism (`enableServiceLinks` and service-link env injection).

The app manifest's `hostAliases` is the **same M8 pattern** (pin
`host.docker.internal` to your node-resolved host IP so the pod can reach host
Ollama) but is **not** a designed-wrong exhibit here — set it to your `getent`
result before applying; the lab shows the command.

## Checks

- `checks.json` — the lab end-state: cluster up + model server Running, the app
  OTel-instrumented and answering on the cluster, the Phoenix exhibit present in
  the manifest, the full observability stack Running **after** the env fix, the
  Prometheus scrape target `up`, the Grafana dashboard provisioned by uid, an
  `/ask` through the cluster producing a Phoenix trace, and the reused M3
  loadtest running bounded. Heavy steps **self-seed** (`make k8s-up`, seed the
  kits, build+load the image, regenerate the corpus ConfigMap from `./corpus`,
  apply with the host-IP `hostAliases` resolved and the `PHOENIX_PORT` env fix
  injected). Every check exports `KUBECONFIG=labs/opsmate/k8s/kubeconfig`;
  assertions are shape-true, not value-exact.
- `deep-dive.checks.json` — the Deep Dive page: the llamacpp metric families are
  real (read off the running engine), the OTel deps are pinned by major, the
  per-request usage block is complete (the cost raw material), the cost formula
  arithmetic holds, and the sampling section names head vs tail sampling.

## Isolation & persistence (unchanged from M8/M9)

- **Isolated kubeconfig** at `labs/opsmate/k8s/kubeconfig` — every `kubectl`
  carries `--kubeconfig`; the default context is never touched.
- **Registry data persists** on `labs/opsmate/data/zot`; teardown deletes the
  cluster only. The manifests and the dashboard JSON stay in `labs/`.
- **One stack at a time**: the Compose model service is DOWN; only `registry`
  runs alongside KIND. The observability stack + app + model fit the 8 GB path
  (spike-measured 2.25 GiB for cluster+model+prom+phoenix; Grafana ~300 MB, the
  app ~256 MiB).
