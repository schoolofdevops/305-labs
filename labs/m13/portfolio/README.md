# OpsMate LLMOps Platform — Portfolio Artifact

> This is a **skeleton**. Fill it with **your** run from the M13 capstone, publish it
> to a public repo you own, and put the link on your CV. It is the interview-ready
> evidence that you can *operate* a language model in production — not a certificate,
> a working platform you assembled and can walk someone through.

A hiring manager reading this repo should be able to answer, from the artifacts alone:
*can this person take a model from raw weights to a governed, observable, gated
production service — and prove each step happened?* Every directory below is one part
of that answer.

## What goes where

| Directory | What you put here | Where it comes from |
| --- | --- | --- |
| `manifests/` | The Kubernetes manifests that serve OpsMate: the model-server Deployment/Service, the autoscaler (KEDA ScaledObject), and the Argo CD Application(s) that reconcile them. | `labs/opsmate/k8s/` (M8–M11) |
| `dashboards/` | The Grafana dashboard JSON for the serving SLOs (latency, queue depth, tokens/s) you built in M10. Export it from Grafana; commit the JSON. | M10 observability |
| `ci/` | The eval-gate CI: the GitHub Actions workflow and/or the Argo Workflows step that block a promotion on `gate.sh`. This is the proof that promotion is *gated*, not manual. | `labs/m12/eval-gate/` (M12) |
| `eval-report/` | The written eval report: the baseline, the candidate's measured numbers, the gate verdict, and one honest paragraph on what you learned. Use `eval-report/REPORT.template.md`. | M5 baseline + M12/M13 gate run |
| `MODELKIT.md` | The signed ModelKit reference **by digest** (not by tag — a digest is immutable), plus the `cosign verify` command that proves the signature. | M7 packaging + signing |

## The rubric (score yourself before you publish)

A complete portfolio artifact scores every row. Aim for all five.

| # | Criterion | Evidence it is met |
| --- | --- | --- |
| 1 | **Reproducible serving** | The manifests apply cleanly and serve the model; a reader could `kubectl apply` them against a KIND cluster and get a working `/health`. |
| 2 | **Observable** | The dashboard JSON loads in Grafana and shows real panels (latency, queue depth) wired to the serving metrics — not an empty template. |
| 3 | **Gated promotion** | The CI file runs `gate.sh` and blocks on its exit code; the eval report shows a real gate verdict (PROMOTE or BLOCK — a BLOCK is a *strong* artifact: it proves the gate works). |
| 4 | **Signed & versioned** | `MODELKIT.md` references the kit by digest and the `cosign verify` command succeeds; the version is semantic (`1.2.0`), not `latest`. |
| 5 | **Honest write-up** | The eval report states what the numbers were, whether the candidate beat the baseline, and what you would do next — no inflated claims. |

## The learner capstone assignment

The strongest version of this artifact is **not** OpsMate — it is the same lifecycle run on
**your own corpus**, any domain you know (your team's runbooks, a product's docs, a hobby
you can write authoritative text about). Swap the corpus, re-run synthesize → tune → pack →
sign → gate → serve, and fill this skeleton with that run. A portfolio piece on a domain you
can speak to in an interview beats a copy of the course's example. Publish it; share it in the
course community showcase.

> **Publishing is yours to do.** The course does not push this repo anywhere — a public repo
> under your name is your decision. When you are ready: create the public repo, copy this
> filled-in `portfolio/` tree into it, and push.
