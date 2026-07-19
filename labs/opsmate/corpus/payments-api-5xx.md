# Payments API — Elevated 5xx Rate

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- The `payments-api` service returns HTTP 500 and 503 responses to a rising share of requests.
- The checkout page shows "We could not process your payment, please retry."
- Grafana panel `payments-api / http_5xx_ratio` climbs above the 2% alert line.
- Latency on the `/charge` endpoint rises before the error rate does.

## Most likely cause

Nine times out of ten this is **database connection-pool exhaustion**, not a code bug. The
`payments-api` holds a bounded pool of connections to the `payments-db` Postgres primary. When
downstream queries slow down, connections are held longer, the pool drains, and new requests fail
fast with a 500 because no connection is free to borrow.

## Diagnosis

1. Check the pool gauge: `curl -s http://payments-api:9102/metrics | grep db_pool_in_use`. A value
   pinned at the pool maximum confirms exhaustion.
2. Check the database for slow or blocked queries:
   `SELECT pid, state, wait_event_type, query_start FROM pg_stat_activity WHERE state <> 'idle';`
3. Look for a long-running migration or an unindexed query introduced by the last deploy.

## Resolution

- If a single slow query is holding connections, cancel it: `SELECT pg_cancel_backend(<pid>);`.
- If the pool is simply undersized for current traffic, raise `DB_POOL_MAX` from 20 to 40 and
  restart the service pods one at a time (rolling restart, never all at once).
- If a recent deploy introduced the slow query, roll back to the previous image (see the
  deploy-rollback runbook) and re-open the change under review.

## Verification

- `http_5xx_ratio` falls back under 1% within five minutes.
- `db_pool_in_use` sits well below the pool maximum at peak.
- The checkout flow completes a test transaction end to end.

## Escalation

If the pool is healthy and 5xx persists, the fault is upstream (the card processor) — escalate to
the Payments on-call and open a vendor ticket. Do not keep restarting pods; it will not help.
