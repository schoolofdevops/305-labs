# OpsMate capacity worksheet — book the hall before you sign the contract

Fill this in **before** you write the memory limit in `model-server.yaml` (Lab Step 2).
The manifest's `resources` block is the hall you book; this sheet is the guest count
you do first. Every number here comes from M1/M2 — you are applying, not deriving.

## The three-term sum

The memory a model server pins down = **weights + runtime buffers + KV cache**.

```
weights   : parameters × bytes-per-parameter
            Qwen3-0.6B at Q8_0 (≈1 byte/param)          ≈ 0.65 GiB   (FIXED — same at 1 user or 50)

runtime   : engine activation scratch + compute graph
            llama-server, this model                     ≈ 0.30 GiB   (roughly fixed)

KV cache  : 112 KiB/token  ×  context length  ×  concurrency     (GROWS with load — M1)
            ctx = 2048, concurrency = 1  →  112 KiB × 2048 × 1    ≈ 0.22 GiB
            ctx = 2048, concurrency = 8  →  112 KiB × 2048 × 8    ≈ 1.75 GiB
            ctx = 8192, concurrency = 1  →  112 KiB × 8192 × 1    ≈ 0.88 GiB   (the context lever)
```

**Single-request working set** = 0.65 + 0.30 + 0.22 ≈ **1.17 GiB**
**8-concurrent working set**   = 0.65 + 0.30 + 1.75 ≈ **2.70 GiB**   (tight on a shared 8 GB box)

## The manifest answers — DERIVED from the sum, not copied

Fill these in and commit them; the lab's check reads these three lines.

- requests.memory = ___   (weights 0.65 + runtime 0.30 + KV@2048×1 0.22 ≈ 1.17 GiB — the honest at-rest working set the scheduler reserves)
- limits.memory = ___      (ceiling before the kernel OOM-kills the pod; holds single-request work with headroom, but tight at 8× concurrency → that is the M9 scale-out signal)
- replicas = ___        (one pod's KV budget holds this concurrency; add a replica when requests_deferred climbs — M9)
- context (-c)    = 2048     (the lever: KV scales linearly with it; bump to 8192 and the KV term quadruples)

## The knobs, restated

| If the box will not fit ... | pull this lever | effect on the sum |
| --- | --- | --- |
| too little memory | lower the **context** (`-c`) | shrinks the KV term directly (linear) |
| more concurrent users needed | add a **replica** (M9) | each replica gets its own KV budget |
| weights too large | lower **precision** (quantize) or smaller model (M2) | shrinks the fixed weights term |

The point: `limits.memory` is a number you can defend, because you computed it here.
A limit copied from another service's YAML is a guess, and for a model server a wrong
guess is a crash loop on the third concurrent user.

<!-- Reference answers (derive first, then check): requests.memory=1200Mi, limits.memory=2Gi, replicas=1 -->
