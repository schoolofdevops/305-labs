# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx", "chromadb"]
# ///
"""M4 deep-dive: the chunking trade-off, measured.

Re-chunks the SAME corpus at three token caps (100 / 300 / 800), builds a
throwaway in-memory Chroma index for each, runs the same query, and prints the
top hit and distance per cap — so you can watch how chunk size moves retrieval.
Too small: fragments, context lost. Too big: blurry averages, weaker distances.

This does NOT touch the lab's persistent index — it uses ephemeral in-memory
clients so you can experiment freely.

Usage:
  uv run labs/m4/rechunk_probe.py "website throwing 500 errors"
"""
import os
import re
import sys
import glob
import httpx
import chromadb

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CORPUS_DIR = os.environ.get("CORPUS_DIR", "labs/opsmate/corpus")
CAPS = [100, 300, 800]


def embed(texts):
    r = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=180.0,
    )
    r.raise_for_status()
    return r.json()["embeddings"]


def chunk(text, source, cap):
    parts = re.split(r"(?m)^(?=##\s)", text)
    out = []
    for part in parts:
        body = part.strip()
        if not body:
            continue
        heading_m = re.match(r"##\s*(.+)", body)
        heading = heading_m.group(1).strip() if heading_m else source
        words = body.split()
        if len(words) <= cap:
            out.append((source, heading, body))
        else:
            for i in range(0, len(words), cap):
                out.append((source, heading, " ".join(words[i : i + cap])))
    return out


def build_and_query(cap, query):
    files = sorted(glob.glob(os.path.join(CORPUS_DIR, "*.md")))
    chunks = []
    for path in files:
        source = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            chunks.extend(chunk(fh.read(), source, cap))
    client = chromadb.EphemeralClient()
    col = client.create_collection(
        name=f"cap{cap}", metadata={"hnsw:space": "cosine"}
    )
    docs = [c[2] for c in chunks]
    col.add(
        ids=[f"{i}" for i in range(len(chunks))],
        documents=docs,
        metadatas=[{"source": c[0], "heading": c[1]} for c in chunks],
        embeddings=embed(docs),
    )
    res = col.query(query_embeddings=[embed([query])[0]], n_results=1)
    return len(chunks), res["metadatas"][0][0], res["distances"][0][0]


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "website throwing 500 errors"
    print(f"query: {query!r}\n")
    print(f"{'cap':>5}  {'chunks':>7}  {'top source':<24} {'heading':<18} {'distance':>8}")
    for cap in CAPS:
        n, meta, dist = build_and_query(cap, query)
        print(
            f"{cap:>5}  {n:>7}  {meta['source']:<24} {meta['heading'][:16]:<18} {dist:>8.4f}"
        )
    print(
        "\nread the shape: very small caps fragment the section (weaker, noisier match);"
        "\nvery large caps average a whole runbook into one blurry vector (distance rises)."
    )


if __name__ == "__main__":
    main()
