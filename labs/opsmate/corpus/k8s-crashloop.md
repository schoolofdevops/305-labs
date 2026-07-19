# Pod CrashLoopBackOff

Fictional runbook for the OpsMate course. Company: Meridian Retail (fictional).

## Symptoms

- A pod cycles through `Running` and `CrashLoopBackOff`, with a rising restart count.
- The Deployment never reaches its desired ready replica count.
- `kubectl get pods` shows `RESTARTS` climbing with a back-off delay between attempts.

## Most likely cause

The container starts and then exits non-zero, and Kubernetes restarts it with an exponential
back-off. The four common roots are a **bad config or missing env var / secret**, a **failed
dependency at startup** (it cannot reach the database), an **OOM kill** (the container exceeds its
memory limit), and a **failing liveness probe** killing a container that is actually still starting.

## Diagnosis

1. Read the last crash's logs — the *previous* container, not the current one:
   `kubectl logs <pod> --previous`.
2. Describe the pod for the exit reason and probe events:
   `kubectl describe pod <pod>` — look for `Last State: Terminated`, `Reason: OOMKilled` or
   `Error`, and any liveness-probe failure events.
3. Check the resource limits against actual usage — an `OOMKilled` reason means the memory limit is
   too low or there is a leak.

## Resolution

- **Config / secret:** fix the missing or wrong env var / mounted secret and let it restart.
- **Startup dependency:** if it crashes because a dependency is not ready, add a proper readiness
  gate or a startup probe with enough `failureThreshold` to cover cold starts.
- **OOMKilled:** raise the memory limit if the usage is legitimate, or fix the leak if it is not.
- **Liveness too aggressive:** loosen the liveness probe's `initialDelaySeconds` /
  `failureThreshold` so it stops killing a slow-but-healthy start.

## Verification

- The pod reaches `Running` and stays there — restart count stops climbing.
- The Deployment reports all replicas ready.
- The application health endpoint returns healthy from inside the cluster.

## Escalation

If the logs show a clean start followed by an unexplained kill with no OOM and no probe failure,
suspect the node — escalate to the platform on-call to check node health and eviction events.
