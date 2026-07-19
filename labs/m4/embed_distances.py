# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""Embed a few texts via host Ollama (nomic-embed-text) and print the pairwise
cosine distances between them — the everyday near/near/far demo from the M4
lesson, in real numbers. No vector DB, no app: just the embedding model and a
distance, so you can feel what "meaning as coordinates" means.

Usage:
  uv run labs/m4/embed_distances.py "text one" "text two" "text three"

Env:
  OLLAMA_URL   host Ollama base URL (default http://localhost:11434)
  EMBED_MODEL  embedding model      (default nomic-embed-text)
"""
import os
import sys
import math
import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


def embed(texts: list[str]) -> list[list[float]]:
    resp = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


def label(d: float) -> str:
    # A rough reading aid, not a hard threshold — the point is near vs far.
    return "near    " if d < 0.6 else "far     "


def main() -> None:
    texts = sys.argv[1:]
    if len(texts) < 2:
        print("give at least two texts to compare", file=sys.stderr)
        sys.exit(2)

    print(f"embedding {len(texts)} texts via {EMBED_MODEL} (768-dim)...\n")
    vecs = embed(texts)
    for i, t in enumerate(texts):
        print(f"  [{i}] {t}")
    print(
        "\npairwise cosine distance (0 = identical meaning, larger = less related):"
    )
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            d = cosine_distance(vecs[i], vecs[j])
            note = "(same meaning, almost no shared words)" if d < 0.6 else "(unrelated)"
            print(f"  [{i}]—[{j}]  {d:.2f}   {label(d)} {note}")


if __name__ == "__main__":
    main()
