# Runbook: Redis Cache Eviction Storm

**Symptom.** The `catalog-api` p99 latency jumps 5–10x and the app logs fill with
`cache miss` warnings. The Redis cache in front of the catalog database is evicting keys
faster than the app can repopulate them, so nearly every request falls through to the
(slow) database. Grafana shows `redis_evicted_keys_total` climbing steeply and the cache
hit ratio collapsing toward zero.

## Cause

Redis is at its `maxmemory` limit and its eviction policy is reclaiming memory by
dropping keys. The two common triggers:

1. **A new feature enlarged the cached objects** (bigger values, same key count) and the
   working set no longer fits in `maxmemory`.
2. **A traffic spike widened the key space** (many distinct queries), so the cache can no
   longer hold the hot set.

Under `allkeys-lru`, Redis evicts the least-recently-used keys to make room. When the
working set exceeds memory, eviction and repopulation fight each other and the hit ratio
craters — a **cache eviction storm**.

## Diagnosis

Check the eviction counter and memory pressure:

```
redis-cli INFO stats | grep evicted_keys
redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_human'
redis-cli INFO stats | grep keyspace_hits
```

A rising `evicted_keys`, `used_memory` pinned at `maxmemory`, and a falling
`keyspace_hits` ratio confirm the storm.

## Fix

Short term, take pressure off the cache:

1. **Raise `maxmemory`** if the host has headroom — give the working set room to fit.
2. **Shorten TTLs on low-value keys** so cold data expires instead of being evicted at
   random, keeping the hot set resident.
3. **Shed load** — if a single bad query pattern is widening the key space, rate-limit or
   fix it at the source.

Long term, right-size the cache to the working set and alert on the eviction rate
(`redis_evicted_keys_total`) *before* the hit ratio collapses — evictions are the leading
indicator, latency is the lagging one.

## Escalation

If raising `maxmemory` is not possible and the hit ratio stays below 50% for more than 15
minutes, page the platform on-call: sustained cache bypass can overload the catalog
database and cascade into a broader outage.
