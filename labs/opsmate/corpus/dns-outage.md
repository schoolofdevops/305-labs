# In-Cluster DNS Outage

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- Services fail to reach each other by name: `dial tcp: lookup payments-db on 10.96.0.10:53: no such
  host` or `Temporary failure in name resolution`.
- The failures are intermittent and hit many unrelated services at once — a strong DNS signal.
- Requests by raw IP still work, while requests by hostname fail.

## Most likely cause

The cluster DNS layer (`CoreDNS`) is unhealthy or overloaded. Common triggers: a CoreDNS pod
crash-looping, an undersized CoreDNS replica count for the query volume, or a bad `Corefile` change
that broke upstream forwarding.

## Diagnosis

1. Check CoreDNS health: `kubectl -n kube-system get pods -l k8s-app=kube-dns`. Any pod not
   `Running`, or restarting, is the lead.
2. Test resolution from inside the cluster:
   `kubectl run -it --rm dnstest --image=busybox --restart=Never -- nslookup payments-db`.
3. Read CoreDNS logs for `SERVFAIL` or upstream timeouts:
   `kubectl -n kube-system logs -l k8s-app=kube-dns --tail=100`.

## Resolution

- If a CoreDNS pod is crash-looping on a bad `Corefile`, revert the ConfigMap to the last good
  version and restart the CoreDNS deployment.
- If CoreDNS is simply overloaded, scale it up: `kubectl -n kube-system scale deploy/coredns
  --replicas=4` and enable autoscaling for it.
- If upstream forwarding is failing, confirm the node's `/etc/resolv.conf` upstream is reachable.

## Verification

- `nslookup` from a test pod resolves in-cluster names cleanly.
- CoreDNS pods are all `Running` with no recent restarts.
- The dependent services' error rates return to baseline.

## Escalation

If DNS is healthy but name resolution still fails for one namespace only, suspect a NetworkPolicy
blocking port 53 — escalate to the platform networking on-call.
