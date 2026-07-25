# M13 lab assets — Agentic Bridge & Capstone

This module has two halves, and this folder backs both.

**Part A — the agentic bridge.** OpsMate v3.5: a tool-using agent that inspects a live
cluster to diagnose a crashlooping pod, every model call going through the M12 gateway.
The cluster is the *subject* being inspected, not a model server — chat stays on host
Ollama through the gateway.

**Part B — the capstone.** The whole course replayed end to end: a new runbook →
synthesize → fine-tune v1.2 → pack + sign `1.2.0` → `gate.sh` → PR promote → Argo sync →
verify, then assemble the portfolio artifact.

| Path | What it is |
| --- | --- |
| `labs/opsmate/mcp/mcp_k8s.py` | The **MCP server**: JSON-RPC 2.0 over stdio, ~80 lines of stdlib, `initialize` / `tools/list` / `tools/call`. Two **read-only** tools (`get_pod_status`, `get_pod_logs`) that shell out to `kubectl` against the isolated kubeconfig. No mutating verb exists in it — the visitor-badge discipline as tool design. Lives under `opsmate/` because it is part of the platform, not just this lab. |
| `labs/m13/agent.py` | The **agent glue**: spawn the MCP server, list tools, convert MCP schemas to OpenAI tool schemas, run turn 1 with tools (the model decides) → execute the call via MCP → answer turn with tools **omitted** (the loop fix). Stdlib only; the loop is bare on purpose so the mechanism is visible. |
| `labs/m13/crashloop.yaml` | The **subject**: a busybox `payments-api` Deployment in namespace `shop` that logs a `FATAL` db-connection line and exits 1, landing in CrashLoopBackOff. The thing the agent diagnoses. |
| `labs/m13/cache-eviction.md` | The **new runbook** the capstone ingests — a small, realistic incident doc that becomes v1.2's training signal. |
| `labs/m13/portfolio/` | The **portfolio-artifact skeleton**: README + rubric, `MODELKIT.md`, an eval-report template, and dirs for `manifests/`, `dashboards/`, `ci/`, `eval-report/`. The learner fills it with their own run and publishes it. |
| `labs/m13/checks.json` | The agentic-half success end-state (needs `KUBECONFIG` — the cluster is up with the crashloop pod, the MCP server is read-only, the agent runs the omit-tools loop). |
| `labs/m13/deep-dive.checks.json` | The Deep Dive page's checks (loop mechanics, dropped-knob translation, constrained decoding, capstone ops notes). |

## The agentic chain (Part A)

```
question -> agent.py
  turn 1 (tools offered) --gateway--> model DECIDES  (finish_reason: tool_calls)
  tools/call            --stdio----> MCP server -> kubectl (read-only) -> live cluster
  answer turn (tools OMITTED) --gateway--> grounded diagnosis
```

Three designed exhibits, all spike-proven, taught live in the lab:

- **A — the agent loop.** Leave `tools` in the request on the answer turn and the gateway
  path re-calls the tool forever. Watch the spend rows accumulate. Fix: omit the tools.
- **B — the silently-dropped knob.** `tool_choice: "none"` *should* suppress tool calls
  but is dropped on the LiteLLM→Ollama path (an M2 compatibility-drift echo at the
  gateway tier). Omitting the tools is the fix that survives translation.
- **arg hygiene** — the model sometimes emits `"pod": "pod payments-api"`; the server
  strips the noise defensively. Defensive parsing is part of the tool contract.

## Isolation & the read-only guarantee

- **Isolated kubeconfig** at `labs/opsmate/k8s/kubeconfig` — every `kubectl`, the MCP
  server, and the agent carry it via `KUBECONFIG`; the default context is never touched.
- **Read-only by construction** — `mcp_k8s.py` calls only `kubectl get` / `kubectl logs`.
  There is no create/delete/patch/scale path in the server, so the agent cannot mutate the
  cluster even if the model asks it to.

## Teardown

The module ends with a **full** teardown — the KIND cluster, the gateway stack, and the
compose app all down — returning the machine to the clean state the course started from.
See the lab's final step.
