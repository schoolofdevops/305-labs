# Message Queue Backlog

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- The order-processing queue depth climbs and does not drain: `orders_queue_depth` rises steadily.
- Downstream effects lag — confirmation emails are late, inventory counts are stale.
- Consumer lag on the topic grows while producers keep publishing at a normal rate.

## Most likely cause

Consumers are not keeping up with producers. Either the consumers are **too few** for the current
publish rate, they are **stuck** (crash-looping or blocked on a slow dependency), or a **poison
message** is repeatedly failing and blocking the partition behind it.

## Diagnosis

1. Read the lag: `orders_queue_depth` and per-consumer-group lag on the broker dashboard. A flat-high
   lag with healthy consumers points at under-provisioning; a growing lag with a stuck consumer
   points at a block.
2. Check consumer health — are the consumer pods `Running` and actually committing offsets, or
   crash-looping?
3. Look for a poison message: a single offset the consumer retries forever. The consumer logs the
   same message id failing on a loop.

## Resolution

- **Under-provisioned:** scale consumers out (add replicas / partitions) until drain rate exceeds
  publish rate. Watch the depth turn over and start falling.
- **Stuck consumer:** fix or restart the blocked consumer; if it is blocked on a slow downstream,
  address that first — more consumers will not help if the downstream is the bottleneck.
- **Poison message:** route the failing message to a dead-letter queue so the partition can advance,
  then investigate the message off the hot path.

## Verification

- Queue depth turns over and trends back toward zero.
- Consumer lag falls and holds near baseline.
- Downstream effects (emails, inventory) catch up.

## Prevention

Alert on queue depth *rate of change*, not just absolute depth — a fast-rising queue is a problem
long before it hits a scary absolute number. Always configure a dead-letter queue so one bad message
cannot stall a partition.
