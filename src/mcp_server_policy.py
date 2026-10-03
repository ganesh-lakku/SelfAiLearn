"""
mcp_server_policy.py — MCP Server 1: Policy Document Search

Exposes via Model Context Protocol (JSON-RPC 2.0 over stdio):
  - search_policy_exclusions  : Search endorsement library for exclusion clauses
  - compute_payout            : Calculate net payable amount after excess deduction

This is the EXISTING "own server" the agent already connects to.
It does NOT call any LLM — it only exposes capabilities.
The host (mcp_agent.py) runs the model; this server exposes data.
"""

import sys
import os
import json

# ── Ensure src/ is on path ────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from tools import search_policy_exclusions as _search, compute_payout as _compute

SERVER_INFO = {
    "name": "policy-search",
    "version": "1.0.0",
    "description": "Policy endorsement library: exclusion search and payout calculation",
}

# ── Tool specifications (docstrings written as prompts) ───────────────────────
TOOLS = [
    {
        "name": "search_policy_exclusions",
        # IMPROVED DOCSTRING — written as a prompt so the model knows when and
        # how to call this tool, what to supply, and how to handle errors.
        "description": (
            "Search the homeowners-policy endorsement library for exclusion clauses "
            "that match the described cause of loss. "
            "Call this whenever adjuster notes mention a specific peril — seepage, "
            "mold, earthquake, sinkhole, or business pursuits — to confirm whether an "
            "exclusion applies before computing the payout. "
            "Supply the exact policy-form number from the claim record (e.g. HO-0304, "
            "HO-0308) and a short peril phrase (e.g. 'continuous seepage', 'earth "
            "movement'). "
            "If the form number is not in the library the server returns the list of "
            "valid forms so you can correct it and retry. "
            "Do NOT guess coverage without calling this tool on dynamic-dependency claims."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_form": {
                    "type": "string",
                    "description": "Policy endorsement form number, e.g. 'HO-0304'. Must match the form_number field in the claim record.",
                },
                "query": {
                    "type": "string",
                    "description": "Short peril phrase to search for, e.g. 'continuous seepage', 'earthquake tremors', 'business pursuits'.",
                },
            },
            "required": ["policy_form", "query"],
        },
    },
    {
        "name": "compute_payout",
        "description": (
            "Calculate the net payable claim amount by deducting the policy excess "
            "from the claimed amount, based on the coverage status. "
            "Call this as the FINAL step after coverage status is determined. "
            "Use the claimed_amount and excess_amount from the claim record exactly — "
            "do not estimate or round. "
            "Status must be one of COVERED, DENIED, or PARTIALLY_COVERED. "
            "Returns payable_amount = 0 for DENIED claims."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claimed_amount": {
                    "type": "number",
                    "description": "Total claimed repair or loss amount in dollars (from claim record).",
                },
                "excess_amount": {
                    "type": "number",
                    "description": "Policy deductible / excess amount in dollars (from claim record).",
                },
                "status": {
                    "type": "string",
                    "enum": ["COVERED", "DENIED", "PARTIALLY_COVERED"],
                    "description": "Coverage determination: COVERED, DENIED, or PARTIALLY_COVERED.",
                },
            },
            "required": ["claimed_amount", "excess_amount", "status"],
        },
    },
]


# ── Minimal JSON-RPC 2.0 over stdio framing ───────────────────────────────────

def read_message():
    """Read one JSON-RPC message from stdin using Content-Length framing."""
    headers = {}
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            return None
        line = raw.decode("utf-8").strip()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    length = int(headers.get("Content-Length", 0))
    if length == 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def write_message(obj):
    """Write one JSON-RPC message to stdout using Content-Length framing."""
    body = json.dumps(obj).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8") + body)
    sys.stdout.buffer.flush()


def make_response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ── Dispatch ──────────────────────────────────────────────────────────────────

def handle_call(name: str, args: dict) -> dict:
    """Execute a tool and return the MCP content response."""
    if name == "search_policy_exclusions":
        result = _search(
            policy_form=args.get("policy_form", ""),
            query=args.get("query", ""),
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    elif name == "compute_payout":
        result = _compute(
            claimed_amount=args.get("claimed_amount", 0.0),
            excess_amount=args.get("excess_amount", 0.0),
            status=args.get("status", "DENIED"),
        )
        return {"content": [{"type": "text", "text": json.dumps(result)}]}

    else:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
            "isError": True,
        }


def main():
    while True:
        msg = read_message()
        if msg is None:
            break

        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            write_message(make_response(req_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            }))

        elif method == "notifications/initialized":
            # Notification — no response needed
            pass

        elif method == "tools/list":
            write_message(make_response(req_id, {"tools": TOOLS}))

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_call(tool_name, arguments)
            write_message(make_response(req_id, result))

        elif method == "ping":
            write_message(make_response(req_id, {}))

        else:
            if req_id is not None:
                write_message(make_error(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
