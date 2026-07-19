# Database Failover (Postgres Primary)

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- Writes fail while reads still work: `cannot execute INSERT in a read-only transaction`.
- The application logs a lost connection to the primary, then repeated reconnect failures.
- The `pg_is_in_recovery()` check returns `t` on a node the application thinks is the primary.

## Most likely cause

The Postgres primary became unavailable — a node crash, a zone outage, or a hung primary — and the
failover controller either has not promoted a replica yet, or promoted one the application is not
pointing at.

## Diagnosis

1. Find the real primary: on each candidate run `SELECT pg_is_in_recovery();` — the primary returns
   `f`, replicas return `t`.
2. Check the failover controller (Patroni / repmgr) state:
   `patronictl -c /etc/patroni.yml list` shows which member holds the leader lock.
3. Confirm replication lag on the promoted node was low before promotion — a high-lag promotion
   means possible data loss to reconcile.

## Resolution

- If a replica is healthy but not promoted, trigger a controlled failover through the controller,
  never by editing `recovery.conf` by hand under pressure.
- Once a new primary holds the leader lock, update the connection endpoint (the service or the
  connection-pooler config) to point at it, then roll the application pods to reconnect.
- If the old primary returns, do NOT let it rejoin as a primary — reprovision it as a replica to
  avoid a split brain.

## Verification

- A test `INSERT` succeeds against the application's write endpoint.
- Exactly one node reports `pg_is_in_recovery() = f`.
- Replication to the remaining replicas resumes and lag falls to near zero.

## Escalation

Any suspected split brain (two primaries) or data-loss window from a high-lag promotion is a
DBA-on-call page, immediately. Stop writes until it is resolved.
