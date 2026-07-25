#!/usr/bin/env python3
"""OpsMate K8s Inspector — a minimal, READ-ONLY MCP server (stdio transport).

MCP is JSON-RPC 2.0 over stdio: the client sends initialize / tools/list /
tools/call requests on stdin; the server answers on stdout. That is the whole
"USB-C of tools" trick — any MCP client can now use this inspector without
knowing kubectl exists. Python stdlib only; every tool is a read-only kubectl
call against the ISOLATED course kubeconfig (the visitor badge, never the
master key — no create/delete/patch verbs exist here at all).
"""
import json, os, subprocess, sys

KUBECONFIG = os.environ.get("KUBECONFIG", "labs/opsmate/k8s/kubeconfig")

def kubectl(*args):
    out = subprocess.run(["kubectl", "--kubeconfig", KUBECONFIG, *args],
                         capture_output=True, text=True, timeout=30)
    return out.stdout.strip() if out.returncode == 0 else f"ERROR: {out.stderr.strip()}"

TOOLS = [
    {"name": "get_pod_status",
     "description": "Live status of pods in a namespace: phase, readiness, restart count, last state.",
     "inputSchema": {"type": "object",
                     "properties": {"namespace": {"type": "string"},
                                    "pod": {"type": "string", "description": "pod name or prefix (optional)"}},
                     "required": ["namespace"]}},
    {"name": "get_pod_logs",
     "description": "Recent logs (last 20 lines, previous container if crashed) of a pod.",
     "inputSchema": {"type": "object",
                     "properties": {"namespace": {"type": "string"}, "pod": {"type": "string"}},
                     "required": ["namespace", "pod"]}},
]

def call_tool(name, args):
    ns = args.get("namespace", "default")
    pod = (args.get("pod") or "").replace("pod ", "").strip()  # arg-hygiene: models prepend "pod "
    if name == "get_pod_status":
        raw = kubectl("-n", ns, "get", "pods", "-o",
                      "jsonpath={range .items[*]}{.metadata.name}|{.status.phase}|{.status.containerStatuses[0].restartCount}|{.status.containerStatuses[0].lastState}{'\\n'}{end}")
        rows = [r for r in raw.split("\n") if r and (not pod or r.startswith(pod.split("-")[0]))]
        return "\n".join(rows) or f"no pods matching '{pod}' in {ns}"
    if name == "get_pod_logs":
        # resolve prefix → full pod name first
        names = kubectl("-n", ns, "get", "pods", "-o", "name")
        full = next((n.split("/")[1] for n in names.split("\n") if pod and pod.split("-")[0] in n), pod)
        logs = kubectl("-n", ns, "logs", full, "--tail=20", "--previous")
        if logs.startswith("ERROR") or "unable to retrieve" in logs:
            logs = kubectl("-n", ns, "logs", full, "--tail=20")
        return logs
    return f"unknown tool {name}"

def main():
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        rid, method, params = req.get("id"), req.get("method"), req.get("params", {})
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05",
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "opsmate-k8s-inspector", "version": "0.1"}}
        elif method == "notifications/initialized":
            continue  # notification, no reply
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            text = call_tool(params.get("name"), params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": text}]}
        else:
            result = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
