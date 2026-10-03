"""
mcp_server_claims.py — MCP Server 2: Claims System

Exposes via Model Context Protocol (JSON-RPC 2.0 over stdio):
  - get_claim          : Retrieve claim record and adjuster notes by claim number
  - get_adjuster_notes : Retrieve just the adjuster note history for a claim

This is the NEW "claims-system server" added with config only.
Zero lines in mcp_agent.py change when this server is added.
The host runs the model; this server exposes claim data only — it does NOT
call any LLM or make any coverage decision.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
from claims_data import CLAIMS_DATABASE

SERVER_INFO = {
    "name": "claims-system",
    "version": "1.0.0",
    "description": "Claims platform: claim status and adjuster note history by claim number",
}

TOOLS = [
    {
        "name": "get_claim",
        "description": (
            "Retrieve the full claim record — loss date, claimed amount, excess amount, "
            "policy form number, and adjuster notes — for a given claim number. "
            "Always call this FIRST to load the claim before searching exclusions or "
            "computing a payout. "
            "Claim numbers follow the format CLM-YYYY-nnnnn (e.g. CLM-2024-10001). "
            "If the number is not found the server returns the correct format so you "
            "can ask the caller to verify the number rather than guessing coverage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "Claim identifier in CLM-YYYY-nnnnn format, e.g. CLM-2024-10001.",
                },
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "get_adjuster_notes",
        "description": (
            "Retrieve only the adjuster note history for a claim, without the full "
            "financial record. "
            "Use this when you need to re-read notes to identify peril keywords "
            "(seepage, mold, earthquake, business pursuits) without re-loading all "
            "claim fields. "
            "Same format requirement as get_claim: CLM-YYYY-nnnnn."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "Claim identifier in CLM-YYYY-nnnnn format.",
                },
            },
            "required": ["claim_id"],
        },
    },
]


def read_message():
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
    body = json.dumps(obj).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8") + body)
    sys.stdout.buffer.flush()


def make_response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ── RECOVERABLE ERROR PATHS ────────────────────────────────────────────────────
# Old error: "Claim ID 'CLM-2024-88120' does not exist in claims records."
# New error: actionable — tells the model the correct format and asks caller to verify.

def _lookup_claim(claim_id: str) -> dict:
    cid = claim_id.strip()
    if cid not in CLAIMS_DATABASE:
        return {
            "success": False,
            "error": (
                f"Claim {cid} not found. "
                f"Claim numbers look like CLM-YYYY-nnnnn (e.g. CLM-2024-10001). "
                f"Check the number and retry, or ask the caller to verify the claim ID."
            ),
        }
    return CLAIMS_DATABASE[cid]


def handle_call(name: str, args: dict) -> dict:
    if name == "get_claim":
        cid = args.get("claim_id", "")
        record = _lookup_claim(cid)
        if not record.get("success", True) and "error" in record:
            return {
                "content": [{"type": "text", "text": json.dumps(record)}],
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": True,
                "claim_id": record["claim_id"],
                "policy_number": record["policy_number"],
                "form_number": record["form_number"],
                "edition_date": record["edition_date"],
                "date_of_loss": record["date_of_loss"],
                "claimed_amount": record["claimed_amount"],
                "excess_amount": record["excess_amount"],
                "adjuster_notes": record["adjuster_notes"],
            })}],
        }

    elif name == "get_adjuster_notes":
        cid = args.get("claim_id", "")
        record = _lookup_claim(cid)
        if not record.get("success", True) and "error" in record:
            return {
                "content": [{"type": "text", "text": json.dumps(record)}],
                "isError": True,
            }
        return {
            "content": [{"type": "text", "text": json.dumps({
                "success": True,
                "claim_id": record["claim_id"],
                "adjuster_notes": record["adjuster_notes"],
            })}],
        }

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
            pass  # Notification — no response

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
