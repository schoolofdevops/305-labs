# Node Disk Pressure

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- Kubernetes marks a node with the `DiskPressure` condition and starts evicting pods.
- Pods on the affected node move to `Evicted` status; new pods will not schedule there.
- Application logs stop being written, or the database refuses writes with `No space left on device`.

## Most likely cause

A partition crossed its eviction threshold. The three usual culprits are **unrotated logs**,
**a runaway container writing to its writable layer**, and **image and build-cache bloat** on the
container runtime's data directory.

## Diagnosis

1. Find the full filesystem on the node: `df -h` — look for a mount above 85%.
2. Attribute the usage: `du -xh --max-depth=1 /var/lib/docker 2>/dev/null | sort -h | tail`, and
   the same for `/var/log`.
3. Check for a single container writing fast: `docker ps -s` (the `SIZE` column shows writable-layer
   growth), or the equivalent `crictl` command on a containerd node.

## Resolution

- Reclaim runtime space first — it is usually the biggest and the safest:
  `docker image prune -af` and `docker builder prune -af` remove unused images and build cache.
- Rotate or truncate oversized logs; fix the logrotate config that let them grow.
- If one container is writing unbounded to its local layer, restart it with a size-limited volume
  or an `emptyDir` with a `sizeLimit`, and file a bug against the service.

## Verification

- `df -h` shows the partition back below 80%.
- The node's `DiskPressure` condition clears and it becomes schedulable again.
- Evicted pods reschedule and reach `Running`.

## Prevention

Alert on `node_filesystem_avail_bytes` per mount at 80%, not at 95% — by 95% you are already
evicting. Cap log sizes and set a routine image-prune on every node.
