"""
mcp_client.py — Minimal synchronous MCP client (JSON-RPC 2.0 over stdio).

Used by mcp_agent.py to communicate with each MCP server subprocess.
Handles the full initialize → tools/list → tools/call lifecycle.

Architecture reminder:
  - This client spawns a server subprocess and exchanges JSON-RPC messages.
  - The MODEL is never called here — this is pure tool-data transport.
  - The agent (mcp_agent.py) is the host that runs the model.
"""

import subprocess
import json
import os
import sys
from typing import Any, Dict, List, Optional


class MCPClient:
    """
    Synchronous stdio MCP client.
    Spawns the server as a subprocess, drives initialize + tools/list,
    then routes tools/call on demand.
    """

    def __init__(self, name: str, command: str, args: List[str], cwd: str = "."):
        self.name = name
        self._next_id = 1
        env = os.environ.copy()
        # Launch server subprocess
        self._proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,   # suppress server-side log noise
            cwd=cwd,
            env=env,
        )
        self._initialized = False
        self._tools: List[Dict] = []

    # ── Wire framing ──────────────────────────────────────────────────────────

    def _next_req_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _write(self, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._proc.stdin.write(header + body)
        self._proc.stdin.flush()

    def _read(self) -> Optional[dict]:
        headers: Dict[str, str] = {}
        while True:
            raw = self._proc.stdout.readline()
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
        body = self._proc.stdout.read(length)
        return json.loads(body.decode("utf-8"))

    def _request(self, method: str, params: dict = None) -> dict:
        rid = self._next_req_id()
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params:
            msg["params"] = params
        self._write(msg)
        resp = self._read()
        if resp is None:
            raise RuntimeError(f"[{self.name}] No response for method={method}")
        if "error" in resp:
            raise RuntimeError(f"[{self.name}] JSON-RPC error: {resp['error']}")
        return resp.get("result", {})

    def _notify(self, method: str, params: dict = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        self._write(msg)

    # ── MCP lifecycle ─────────────────────────────────────────────────────────

    def initialize(self) -> dict:
        """Send initialize handshake and return server info."""
        result = self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "mcp-agent", "version": "1.0"},
            "capabilities": {},
        })
        self._notify("notifications/initialized")
        self._initialized = True
        return result

    def list_tools(self) -> List[Dict]:
        """Send tools/list and cache the result."""
        result = self._request("tools/list")
        self._tools = result.get("tools", [])
        return self._tools

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Send tools/call and return the parsed result."""
        result = self._request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        # Extract text content from MCP content array
        contents = result.get("content", [])
        if contents and contents[0].get("type") == "text":
            try:
                return json.loads(contents[0]["text"])
            except json.JSONDecodeError:
                return {"raw": contents[0]["text"]}
        return result

    @property
    def tools(self) -> List[Dict]:
        return self._tools

    def close(self) -> None:
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
