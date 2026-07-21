# LLM Stack X-Ray

One live visualizer for the whole course. It reads your **real** stack — no simulation,
no fake numbers — and grows one lens per module.

| Lens | Module | What it shows |
| --- | --- | --- |
| **Tokens** | M1 | A request split into prefill and decode on your real model: live token stream, TTFT (client and server view), TPOT, tok/s, phase-split bar, context-window usage |
| **Engine** | M3 | Your real llama-server's `/metrics`, polled live: requests processing/deferred (watch queueing appear under load), lifetime token counters with rates, decode tok/s trend chart, engine log |
| **RAG** | M4 | Ask your real corpus: Retrieve shows ranked chunks with sources + distances live from your index; Ask runs the full pipeline and marks which chunks fed the answer |
| **Evals** | M5 | The course scoreboard: retrieval tripwire (N/24), the three generation arms (no-RAG / v1 / v2) as bars, the RAG-vs-no-RAG gap, honesty-refusal count, and the per-question pass/fail grid — read live from the eval JSONs your runs write |
| **Train** | M6 | Tails your real `train/progress.jsonl` live: loss curve for the whole run, step/lr/elapsed/sec-per-step gauges, first-vs-latest loss, and the run-complete summary banner |
| **Artifacts** | M7 | Browses your real Zot registry: repos and tags with per-tag SIGNED/unsigned badges (OCI referrers API, sigstore-aware), and per-tag layer tables showing the 610 MB model layer against the KB-sized prompt/dataset layers |
| **K8s** | M8 | Your real cluster via `kubectl proxy` (same-origin, one hop further): pods with phase/ready/restarts, the serving Deployment's replica status, the engine gauges scraped through the Service proxy, and recent events |
| **Traces** | M10 | The case-file view: recent traces from your real Phoenix (probe noise filtered), each opening into a waterfall — ask/retrieve/generate bars on a shared timeline with per-span latency and the LLM span's token count (the per-request bill) |
| Spend | M12 | _lands with M12_ |

## Run it

```bash
bash labs/tools/xray/serve.sh
# open http://127.0.0.1:8010/
```

Ollama must be running (`ollama serve` or the desktop app) with at least one model pulled
(the course model is `qwen3:0.6b`).

## How it works — and why there is no token box

`serve.py` (Python stdlib, zero dependencies) does two jobs from one origin:

1. serves this static page, and
2. forwards `/ollama/*` to your local Ollama server.

Because the page and the API share one origin, the browser applies no CORS wall and the
page never needs a credential — it rides on whatever your local Ollama already allows.
This is the same trick `kubectl proxy` uses for the Kubernetes API, and you will meet it
again in the K8s phase of the course. If a tool ever asks you to paste a secret into a
web page, ask why it didn't do this instead.

Ollama listening elsewhere? `OLLAMA_HOST_URL=http://other-host:11434 bash serve.sh`.
Phoenix elsewhere (Traces lens)? `PHOENIX_URL=http://other-host:16006 bash serve.sh`.
llama-server elsewhere (Engine lens)? `LLAMACPP_URL=http://other-host:8080 bash serve.sh`.
OpsMate app elsewhere (RAG lens)? `APP_URL=http://other-host:8001 bash serve.sh`.

## Connection budget (a design note worth stealing)

Browsers allow ~6 concurrent HTTP/1.1 connections per host. The X-Ray spends **one** on
the active generation stream and **polls** version/models every 10 s — well inside the
budget, leaving room for the lenses later modules add.

## Troubleshooting

| Symptom | Cause · fix |
| --- | --- |
| Red "ollama down" chip + banner | Ollama not running, or listening on a non-default address. Start it; set `OLLAMA_HOST_URL` if needed; reload. |
| Model dropdown says "no models" | Nothing pulled yet: `ollama pull qwen3:0.6b`, wait for the 10 s poll or reload. |
| Port already in use | `PORT=8011 bash serve.sh` and open that port instead. |
| "thinking mode" checkbox seems to change nothing | The selected model is not a thinking-capable model. On `qwen3:*` you will see italic thinking text and a visibly longer TTFT when it is on. |
| Stream stops mid-answer | You clicked Stop, or Ollama unloaded the model (default keep-alive is 5 min — the first request after idle pays the load cost again; watch the *model load* gauge). |
