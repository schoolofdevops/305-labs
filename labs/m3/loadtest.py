#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["httpx>=0.27"]
# ///
"""OpsMate bounded load test — laptop-safe, reads throughput as concurrency rises.

This is NOT a benchmark tool. It sends a fixed, small number of identical chat
requests at rising concurrency (4 → 8 → 16) against one engine and prints, per
level, the throughput and the p50/p95 latency. The teaching point is the SHAPE:
as you add concurrent requests to a single engine, a batching engine keeps
total throughput climbing (or holding) while per-request latency stays sane,
because it processes requests together rather than one after another. Watch the
engine's own /metrics (requests_deferred) climb alongside this — that is the
queue forming.

Every level uses a bounded request count and a hard per-request timeout, so this
never runs away with your laptop. Adjust with the env vars below.

Run it:
    OPENAI_BASE_URL=http://localhost:8080/v1 MODEL=qwen3-0.6b uv run loadtest.py

Env:
    OPENAI_BASE_URL   engine base URL (default http://localhost:8080/v1)
    MODEL             model name to send (default qwen3-0.6b)
    REQUESTS          requests per concurrency level (default 24)
    LEVELS            comma-separated concurrency levels (default 4,8,16)
    MAX_TOKENS        cap each answer so runs stay short (default 48)
    TIMEOUT           per-request timeout seconds (default 60)
"""
import asyncio
import os
import time

import httpx

BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1").rstrip("/")
MODEL = os.environ.get("MODEL", "qwen3-0.6b")
REQUESTS = int(os.environ.get("REQUESTS", "24"))
LEVELS = [int(x) for x in os.environ.get("LEVELS", "4,8,16").split(",")]
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "48"))
TIMEOUT = float(os.environ.get("TIMEOUT", "60"))

PAYLOAD = {
    "model": MODEL,
    "max_tokens": MAX_TOKENS,
    "messages": [
        {"role": "system", "content": "You are OpsMate, a concise SRE assistant. /no_think"},
        {"role": "user", "content": "List two things to check first when a service is returning 503s."},
    ],
}


async def one_request(client: httpx.AsyncClient, sem: asyncio.Semaphore) -> tuple[bool, float]:
    async with sem:
        start = time.perf_counter()
        try:
            r = await client.post("/chat/completions", json=PAYLOAD, timeout=TIMEOUT)
            ok = r.status_code == 200
        except Exception:
            ok = False
        return ok, time.perf_counter() - start


async def run_level(concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        wall_start = time.perf_counter()
        results = await asyncio.gather(
            *(one_request(client, sem) for _ in range(REQUESTS))
        )
        wall = time.perf_counter() - wall_start

    lats = sorted(lat for ok, lat in results if ok)
    ok_count = len(lats)
    if not lats:
        print(f"  concurrency={concurrency:<3} ALL {REQUESTS} REQUESTS FAILED "
              f"(is the engine up at {BASE_URL}?)")
        return
    p50 = lats[int(0.50 * (len(lats) - 1))]
    p95 = lats[int(0.95 * (len(lats) - 1))]
    throughput = ok_count / wall
    print(
        f"  concurrency={concurrency:<3} ok={ok_count}/{REQUESTS}  "
        f"throughput={throughput:5.2f} req/s  "
        f"p50={p50:5.2f}s  p95={p95:5.2f}s  wall={wall:5.2f}s"
    )


async def main() -> None:
    print(f"engine   : {BASE_URL}")
    print(f"model    : {MODEL}")
    print(f"profile  : {REQUESTS} requests/level, levels {LEVELS}, "
          f"max_tokens={MAX_TOKENS}\n")
    print("Rising concurrency against ONE engine. Watch throughput and p95:")
    for level in LEVELS:
        await run_level(level)
    print("\nRead the shape, not the exact numbers: throughput should hold or climb "
          "as\nconcurrency rises while the engine batches. Where it flattens and p95 "
          "grows,\nthe engine is queueing — confirm it live in the /metrics "
          "requests_deferred gauge.")


if __name__ == "__main__":
    asyncio.run(main())
