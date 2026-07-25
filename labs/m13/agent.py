#!/usr/bin/env python3
"""OpsMate agent (v3.5) — the tool-using loop: gateway LLM <-> MCP <-> live cluster.

This is the whole agentic bridge in one readable file. It is NOT a framework —
it is the minimal glue that turns a chat model into an agent that can inspect a
live Kubernetes cluster to answer "why is my pod crashlooping?". Read it top to
bottom; every section is one idea.

The pipeline it drives:

    MCP spawn -> tools/list -> convert MCP schemas to OpenAI tool schemas
      -> turn 1 (tools offered): the model DECIDES which tool to call
      -> execute the tool call via MCP against the live cluster
      -> answer turn (tools OMITTED): the model writes a grounded diagnosis

Two design choices carry the module's sharpest lessons:

  * The schema conversion (load_tools) is the entire "USB-C of tools" trick —
    a mechanical rename of three fields, nothing more.
  * The answer turn omits `tools` ON PURPOSE (see answer()). Leave them in and
    the gateway path re-calls the tool forever — the agent loop. Omitting the
    tools once the data is in hand is how you TERMINATE the loop. Termination is
    the orchestrator's job, not the model's.

The declarative-agent pattern (a persona written as SOUL.md / AGENTS.md /
SKILL.md markdown, the shape the 303-agentops course teaches) is intentionally
NOT rebuilt here. This file keeps the loop bare so the mechanism is visible.

Dependency-light on purpose: Python stdlib only (urllib, subprocess, json).
Run it against the M12 gateway + the M13 crashloop cluster (see the lab).
"""
import json, os, subprocess, sys, urllib.request

# The gateway is the SAME front door from M12: one endpoint, virtual-key auth,
# spend metered per call. The agent's tool-call turns show up as billable rows
# in /spend/logs — the Spend lens (M12) is the agent-cost dashboard for free.
GATEWAY = os.environ.get("GATEWAY_URL", "http://127.0.0.1:4000/v1/chat/completions")
KEY = os.environ.get("GATEWAY_KEY", "sk-master-smoke")
MODEL = os.environ.get("AGENT_MODEL", "opsmate")
HERE = os.path.dirname(os.path.abspath(__file__))

# The question the agent must answer from LIVE cluster data (override via argv).
QUESTION = (sys.argv[1] if len(sys.argv) > 1 else
            "Why is my payments-api pod crashlooping in namespace shop? "
            "Diagnose from live cluster data.")

# A one-line nudge. The 0.6B model tool-calls competently but is frugal — left
# alone it often calls get_pod_status and stops. The system line pushes it to
# gather BOTH signals (status AND logs) before diagnosing, the way an on-call
# engineer would. Prose in the lab stays state-tolerant: your run may call one
# tool or both, and either is a valid trace.
SYSTEM = ("You are OpsMate, an SRE assistant. To diagnose a crashlooping pod, "
          "use the tools to gather BOTH its status (restarts, last state) AND "
          "its recent logs before answering. Ground every claim in tool output.")


# ---------------------------------------------------------------------------
# 1. MCP client — spawn the server, speak JSON-RPC 2.0 over stdio.
# ---------------------------------------------------------------------------
# MCP is not magic: it is line-delimited JSON-RPC on the child's stdin/stdout.
# We start the server as a subprocess and talk to it by writing one JSON request
# per line and reading one JSON response per line. That is the "stdio transport".
_mcp = subprocess.Popen(
    [sys.executable, f"{HERE}/../opsmate/mcp/mcp_k8s.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env={**os.environ})
_rid = 0


def mcp(method, params=None):
    """Send one JSON-RPC request to the MCP server and return its result."""
    global _rid
    _rid += 1
    _mcp.stdin.write(json.dumps(
        {"jsonrpc": "2.0", "id": _rid, "method": method, "params": params or {}}) + "\n")
    _mcp.stdin.flush()
    return json.loads(_mcp.stdout.readline())["result"]


# ---------------------------------------------------------------------------
# 2. Discover the tools and convert MCP schemas to OpenAI tool schemas.
# ---------------------------------------------------------------------------
# THIS is the USB-C beat. MCP describes each tool as {name, description,
# inputSchema}. The OpenAI /chat/completions API wants each tool as
# {type: "function", function: {name, description, parameters}}. The conversion
# is a MECHANICAL rename — inputSchema becomes parameters, wrap it in the
# function envelope. Any MCP server now plugs into any OpenAI-compatible model
# with this same adapter. One plug, any tool. That is the whole point of MCP.
def load_tools():
    init = mcp("initialize")
    print(f"[mcp] connected: {init['serverInfo']['name']} v{init['serverInfo']['version']}")
    mcp_tools = mcp("tools/list")["tools"]
    print(f"[mcp] tools: {[t['name'] for t in mcp_tools]}")
    oai_tools = [{"type": "function",
                  "function": {"name": t["name"],
                               "description": t["description"],
                               "parameters": t["inputSchema"]}}
                 for t in mcp_tools]
    return oai_tools


# ---------------------------------------------------------------------------
# 3. Gateway call — one POST to the OpenAI-compatible endpoint.
# ---------------------------------------------------------------------------
def chat(payload):
    payload = {"model": MODEL, **payload}
    req = urllib.request.Request(
        GATEWAY, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    return json.load(urllib.request.urlopen(req, timeout=240))


# ---------------------------------------------------------------------------
# 4. The agent loop — decide, execute, answer.
# ---------------------------------------------------------------------------
def run():
    tools = load_tools()
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": QUESTION}]

    # --- Turn 1: the model DECIDES. We offer the tools; the model chooses which
    # to call and with what arguments. finish_reason == "tool_calls" means it
    # wants a tool run before it will answer. This is the model's "action space":
    # because the tools are in the request, calling one is a legal next move.
    #
    # `think: False` is load-bearing on this model. qwen3:0.6b is a reasoning
    # model; left thinking-on, it spends its whole token budget on hidden
    # reasoning before it emits the tool call (~2 min for a 22-token call) and
    # returns EMPTY visible content on the answer turn. Disabling thinking makes
    # both turns fast and gives the answer turn actual prose to return. (Ollama's
    # `think` param survives the gateway here — unlike tool_choice; see Exhibit B.)
    d = chat({"messages": msgs, "tools": tools, "think": False, "max_tokens": 600})
    m = d["choices"][0]["message"]
    msgs.append(m)
    calls = m.get("tool_calls") or []
    print(f"[llm] finish={d['choices'][0]['finish_reason']}  tool_calls={len(calls)}  "
          f"({d['usage']['completion_tokens']} tok — a billable turn in /spend/logs)")

    # --- Execute each tool call via MCP against the LIVE cluster. The result
    # comes back as a role:"tool" message the model reads on the next turn.
    for tc in calls:
        fn = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        result = mcp("tools/call", {"name": fn, "arguments": args})["content"][0]["text"]
        print(f"[mcp] {fn}({args}) -> {result[:80].strip()}...")
        msgs.append({"role": "tool", "tool_call_id": tc.get("id", "t"), "content": result})

    # --- The answer turn: tools OMITTED. This is the loop fix, load-bearing.
    #
    # If you pass `tools=` here again, calling a tool is STILL a legal move, so
    # the gateway path re-calls the tool instead of answering — forever. The
    # tool schema in the request IS the invitation; drop the invitation once the
    # data is in hand and the only move left is to write the answer. (The lab
    # shows the loop live, then drops the tools to fix it. tool_choice:"none"
    # LOOKS like the fix but is silently dropped on the LiteLLM->Ollama path —
    # another M2-style compatibility-drift exhibit. Omitting tools is the fix
    # that survives.)
    d2 = chat({"messages": msgs, "think": False, "max_tokens": 1200})
    ans = d2["choices"][0]["message"].get("content") or ""
    print(f"\n[llm] grounded diagnosis ({d2['usage']['completion_tokens']} tok):\n{ans}")
    _mcp.terminate()


if __name__ == "__main__":
    run()
