# Cache Stampede

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- A sudden spike of identical, expensive requests hits the database or an upstream service.
- Latency spikes and error rates rise the moment a popular cache key expires.
- The pattern is periodic — it recurs exactly when a hot key's TTL lapses.

## Most likely cause

A **cache stampede** (also called a thundering herd or dogpile): a heavily-requested cache key
expires, and every concurrent request misses at the same instant, so they all fall through to the
expensive origin at once instead of one recomputing while the rest wait.

## Diagnosis

1. Correlate the latency spike with cache key TTLs. A spike that lands exactly on a key's expiry is
   the tell.
2. Check origin load at the spike: a burst of identical queries for the same key confirms the herd.
3. Confirm the cache hit ratio drops to near zero briefly at each recurrence.

## Resolution

- **Request coalescing (single-flight):** let only the first request recompute a missing key while
  the rest wait for its result. This is the primary fix.
- **Early / probabilistic recomputation:** refresh a hot key *before* it fully expires, so it is
  never simultaneously missing for everyone.
- **Jittered TTLs:** spread expiries so many keys do not lapse on the same tick.

## Verification

- The periodic latency spikes at TTL boundaries disappear.
- Origin load stays flat across cache expiries instead of spiking.
- Cache hit ratio holds steady rather than dropping to zero at each recurrence.

## Prevention

Never give many hot keys the same fixed TTL. Combine single-flight recomputation with jittered
expiries so no popular key can ever miss for all callers at once.
