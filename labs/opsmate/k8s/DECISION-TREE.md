# The serving decision tree — Deployment vs router+canary vs KServe vs llm-d

The one-page capstone artifact for M9. When you serve a model on Kubernetes you
pick ONE of four patterns. They are a ladder of capability against a ladder of
dependency cost — you climb only as far as your problem forces you. This file is
the map; keep it, it is referenced again in the M13 capstone.

## The tree

```
Do you need to shift traffic between two model VERSIONS at once
(canary, A/B, gradual rollout)?
│
├─ NO ──► Do you need scale-to-zero, or a fleet you do not want to
│         hand-manage (many models, autoscaling, standardized rollout)?
│         │
│         ├─ NO ──► (1) PLAIN DEPLOYMENT + SERVICE
│         │          One version, one Service. What M8 built. No extra deps.
│         │
│         └─ YES ─► (3) KServe (InferenceService)
│                    Declarative serving CRD: canaryTrafficPercent, scale-to-zero,
│                    standardized rollout. Costs a dependency stack.
│
└─ YES ──► Is the fleet small and are you on a laptop / a few nodes,
           OR do you need per-token, KV-cache-aware, disaggregated routing
           at scale?
           │
           ├─ small / manual ──► (2) ROUTER + CANARY (split_clients)
           │                      One nginx, a ConfigMap weight, a Service each.
           │                      What M9 built. Cheapest honest split.
           │
           └─ large / cache-aware ──► (4) llm-d / Gateway API Inference Extension
                                      InferencePool + KV-aware, prefix-aware routing,
                                      disaggregated prefill/decode pools. The frontier.
```

## When each pays

| Pattern | Use it when | Do NOT reach for it when | Dependency cost |
| --- | --- | --- | --- |
| **(1) Plain Deployment + Service** (M8) | One model version, no live traffic shifting. The default — start here. | You need to run two versions against real traffic at once. | None beyond core K8s. |
| **(2) Router + canary** (M9, `split_clients`) | You want to canary/A-B two versions on a laptop or a few nodes, and you are happy editing a weight by hand. | You need per-token routing, cache affinity, or scale-to-zero. The split is coarse (per request, by weight) and manual. | One nginx pod (64Mi) + a ConfigMap. Trivial. |
| **(3) KServe** (InferenceService) | You want `canaryTrafficPercent` as a declared field, scale-to-zero, and a standardized rollout across a FLEET of models. | You are on 8 GB / one node and just need one split — the dependency stack outweighs the gain. | Knative + a networking layer + cert-manager (and their upkeep). Real. |
| **(4) llm-d / Gateway API Inference Extension** | You serve at scale and the ROUTING decision itself must be inference-aware — KV-cache/prefix affinity, disaggregated prefill/decode pools (M1's two phases become two pools). | You do not have the scale or the traffic shape that makes cache-aware routing pay. It is the frontier, not the default. | A Gateway API implementation + the inference extension + pool operators. Highest. |

## The rule that governs all four

Climb the ladder only when the problem forces you up a rung. A plain Deployment
serves one version fine; you add a router the day you must run two versions against
real traffic; you adopt KServe when a fleet and scale-to-zero justify its
dependency stack; you reach for llm-d when the routing decision itself has to be
inference-aware at scale. Every rung up buys capability and costs dependencies —
and the two things the router pattern (2) fundamentally CANNOT do, which is why
the frontier (4) exists, are **per-token / cache-aware routing** (nginx splits per
request by a blind hash, it cannot see KV-cache locality) and **prefix affinity**
(sending a request to the pod that already holds its prompt's KV). When those
start to matter, you have outgrown the router.

## The decision this course made, and why

OpsMate is one model, one node, an 8 GB laptop. M8 shipped pattern (1). M9 adds
pattern (2) — a router + canary — because the teachable act is shifting traffic
between two versions and letting the golden set kill the loser, and (2) does that
with a 64Mi nginx you can read end to end. Patterns (3) and (4) are surveyed and
read, not installed: on this hardware their dependency cost is the lesson, not a
step. On a real fleet you would climb to (3); at real scale with cache-sensitive
traffic, to (4).
