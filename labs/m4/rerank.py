# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "chromadb", "sentence-transformers"]
# ///
"""M4 deep-dive: hybrid retrieval + a CPU cross-encoder reranker, measured.

Runs three retrieval strategies against the SAME embedded Chroma index the lab
built, on a small set of gold questions, and prints which source each strategy
puts at rank 1 — so you can see, on real numbers, what a keyword pass and a
cross-encoder reranker change versus plain vector search.

  1. vector      — pure embedding nearest-neighbour (what the app does)
  2. hybrid      — vector candidates, re-scored with a keyword (BM25-ish) overlap
  3. rerank      — vector candidates, re-scored by a CPU cross-encoder

This reads the index at labs/opsmate/data/chroma (built by the lab's /ingest).
The cross-encoder model downloads once (~90 MB) on first run; it runs on CPU.

Usage:
  uv run labs/m4/rerank.py
"""
import os
import re
import math
import httpx
import chromadb

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "labs/opsmate/data/chroma")
CANDIDATES = 8  # how many vector candidates to rerank
TOP = 3

# (question, the source filename we consider the correct top hit) — the gold set.
GOLD = [
    ("website throwing 500 errors", "payments-api-5xx.md"),
    ("cluster names not resolving", "dns-outage.md"),
    ("pod keeps restarting", "k8s-crashloop.md"),
]


def embed(texts):
    r = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def keyword_overlap(query, text):
    """A cheap lexical score: fraction of query terms present in the chunk."""
    q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    t_terms = set(re.findall(r"[a-z0-9]+", text.lower()))
    if not q_terms:
        return 0.0
    return len(q_terms & t_terms) / len(q_terms)


def main():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_or_create_collection(
        name="runbooks", metadata={"hnsw:space": "cosine"}
    )
    if col.count() == 0:
        print(f"index at {CHROMA_DIR} is empty — run the lab's /ingest first.")
        return

    from sentence_transformers import CrossEncoder

    print("loading CPU cross-encoder (ms-marco-MiniLM, ~90 MB first run)...")
    ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    print(f"\ngold set: {len(GOLD)} questions, top-{TOP} kept\n")
    tallies = {"vector": 0, "hybrid": 0, "rerank": 0}

    for q, want in GOLD:
        q_emb = embed([q])[0]
        res = col.query(query_embeddings=[q_emb], n_results=CANDIDATES)
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]

        # 1. vector: already ordered by ascending distance
        vector_rank1 = metas[0]["source"]

        # 2. hybrid: combine vector similarity (1-dist) with keyword overlap
        hybrid = sorted(
            range(len(docs)),
            key=lambda i: (1.0 - dists[i]) + 0.5 * keyword_overlap(q, docs[i]),
            reverse=True,
        )
        hybrid_rank1 = metas[hybrid[0]]["source"]

        # 3. rerank: cross-encoder scores the (query, chunk) pairs directly
        scores = ce.predict([(q, d) for d in docs])
        rerank = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
        rerank_rank1 = metas[rerank[0]]["source"]

        for name, got in (
            ("vector", vector_rank1),
            ("hybrid", hybrid_rank1),
            ("rerank", rerank_rank1),
        ):
            if got == want:
                tallies[name] += 1

        print(f"Q: {q!r}  (want: {want})")
        print(f"    vector rank1: {vector_rank1}")
        print(f"    hybrid rank1: {hybrid_rank1}")
        print(f"    rerank rank1: {rerank_rank1}")

    n = len(GOLD)
    print("\nrank-1 correct (higher is better):")
    for name in ("vector", "hybrid", "rerank"):
        print(f"  {name:7s} {tallies[name]}/{n}")


if __name__ == "__main__":
    main()
