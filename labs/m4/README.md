# M4 lab assets — Embeddings, Vector Databases & RAG

These files back the M4 lab (**Build OpsMate v0.5: RAG over Your Runbooks**) and
its Deep Dive. Run the lab from the rendered course page; this folder is what its
commands reference.

| File | What it is |
| --- | --- |
| `embed_distances.py` | The everyday near/near/far demo. Embeds a few texts via host Ollama (`nomic-embed-text`, 768-dim) and prints their pairwise cosine distances — meaning as coordinates, in real numbers. `uv run labs/m4/embed_distances.py "text a" "text b" "text c"`. |
| `rerank.py` | Deep-dive §2. Runs three retrieval strategies (vector / hybrid keyword / CPU cross-encoder rerank) against the lab's Chroma index on a gold question set and tallies rank-1 correctness — the measured before/after. Downloads a ~90 MB cross-encoder once. |
| `rechunk_probe.py` | Deep-dive §3. Re-chunks the corpus at 100/300/800-token caps into throwaway in-memory indexes, runs the same query, and prints the top hit + distance per cap — the chunking trade-off, measured. Never touches the persistent index. |
| `checks.json` | Machine checks for the lab's success end-state (used by course validation). Self-seeds (pulls the embed model, brings the stack up, ingests) and asserts shapes, not run-specific values. |
| `deep-dive.checks.json` | Machine checks for the Deep Dive page's end-state (reranker + rechunk probe run and report). |

The Python files are `uv`-runnable single scripts — `uv` reads the inline
dependency block and fetches what they need the first time. No virtualenv to manage.

## The RAG stack lives in `labs/opsmate/`

M4 grows the OpsMate spine from one service to three. The new services are defined
in `labs/opsmate/compose.yaml`:

- **`app/`** — the FastAPI RAG backend (`/ingest`, `/retrieve`, `/ask`). Chroma is
  embedded in this process (PersistentClient on the `./data/chroma` volume);
  embeddings come from host Ollama; generation goes through the M3 `model` service.
- **`ui/`** — a Streamlit chat page over the app, with a retrieved-chunks expander.
- **`corpus/`** — twelve short fictional SRE runbooks. Written once here; reused by
  M5's golden question set and M6's synthetic data. One runbook carries a planted
  indirect-prompt-injection payload for the lab's injection exhibit.

Bring the stack up with `make -C labs/opsmate up` and down with
`make -C labs/opsmate down`. Teardown keeps `labs/opsmate/data/chroma` — M5 reuses
the built index for its evals.
