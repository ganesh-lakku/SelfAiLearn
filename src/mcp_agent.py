"""
mcp_agent.py — MCP-aware Claims Triage Agent

Architecture:
  - Reads mcp_config.json to discover which MCP servers to connect to.
  - Connects to each server, sends initialize + tools/list.
  - Aggregates ALL discovered tools and presents them to the LLM.
  - Routes tools/call messages to the correct server automatically.
  - ZERO lines in this file change when a new MCP server is added to the config.
    Adding server two is config-only: mcp_config.json gets one new stanza.

Key separation:
  - MODEL runs HERE (in this host process, via Groq API).
  - MCP servers expose capabilities; they do NOT call the model.
  - Discovery is real: the tool list is read from tools/list at runtime,
    not hardcoded in this file.
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import MCPClient

load_dotenv()

# ── Pricing (same as agent.py) ────────────────────────────────────────────────
INPUT_COST_PER_TOKEN  = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012

DEFAULT_MAX_ITERATIONS  = 8
DEFAULT_MAX_TOKENS      = 16000
DEFAULT_MAX_COST        = 0.10
DEFAULT_MAX_WALL_CLOCK  = 60.0

MODEL_NAME    = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"

MCP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "mcp_config.json")

AGENT_SYSTEM_PROMPT = """You are an autonomous Insurance Claims Triage Agent.
Triage incoming insurance claims by following these steps:
1. Call get_claim with the claim_id to load the loss date, amounts, policy form, and adjuster notes.
2. Read the adjuster notes. If they mention a specific peril or exclusion trigger
   (seepage, mold, earthquake, sinkhole, business pursuits), call search_policy_exclusions
   to verify whether an exclusion applies.
3. Determine coverage status: COVERED, DENIED, or PARTIALLY_COVERED.
4. Call compute_payout with claimed_amount, excess_amount, and status.
5. Output a final summary: Status / Payable Amount / Applicable Exclusion / Rationale.

Use tools in sequence. Do not guess coverage without reading exclusions on exclusion-triggering claims."""


# ── Config loader ─────────────────────────────────────────────────────────────

def load_mcp_config(config_path: str = MCP_CONFIG_PATH) -> Dict[str, Any]:
    """Load MCP server definitions from mcp_config.json."""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Server pool ───────────────────────────────────────────────────────────────

class MCPServerPool:
    """
    Manages a pool of MCP server connections.
    Built entirely from mcp_config.json — no server names or tool names
    are hardcoded in this class.
    """

    def __init__(self, config_path: str = MCP_CONFIG_PATH):
        config = load_mcp_config(config_path)
        servers_cfg = config.get("mcpServers", {})
        self._clients: Dict[str, MCPClient] = {}
        self._tool_to_server: Dict[str, str] = {}   # tool_name → server_name
        self._all_tools: List[Dict] = []

        base_dir = os.path.dirname(os.path.abspath(config_path))

        for server_name, srv_cfg in servers_cfg.items():
            cmd = srv_cfg["command"]
            args = srv_cfg.get("args", [])
            cwd = srv_cfg.get("cwd", base_dir)
            if not os.path.isabs(cwd):
                cwd = os.path.join(base_dir, cwd)

            client = MCPClient(name=server_name, command=cmd, args=args, cwd=cwd)
            client.initialize()
            tools = client.list_tools()

            self._clients[server_name] = client
            for tool in tools:
                self._tool_to_server[tool["name"]] = server_name
                # Convert MCP tool spec → OpenAI function spec
                self._all_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                    },
                })

    @property
    def openai_tools(self) -> List[Dict]:
        """Return discovered tools in OpenAI function-calling format."""
        return self._all_tools

    @property
    def tool_names(self) -> List[str]:
        return list(self._tool_to_server.keys())

    def call(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the correct MCP server."""
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return {"success": False, "error": f"Unknown tool '{tool_name}'"}
        return self._clients[server_name].call_tool(tool_name, arguments)

    def close(self) -> None:
        for client in self._clients.values():
            client.close()


# ── Agent loop ────────────────────────────────────────────────────────────────

def get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=DEFAULT_MAX_WALL_CLOCK,
    )


def run_mcp_agent(
    claim_id: str,
    config_path: str = MCP_CONFIG_PATH,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_cost: float = DEFAULT_MAX_COST,
    max_wall_clock: float = DEFAULT_MAX_WALL_CLOCK,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run the MCP-aware agent for one claim.
    Tools are discovered from mcp_config.json at runtime — not hardcoded here.
    """
    client = get_client()
    pool = MCPServerPool(config_path=config_path)
    start = time.time()

    if verbose:
        print(f"\n[MCP-Agent] Discovered {len(pool.tool_names)} tools from config:")
        for name in pool.tool_names:
            print(f"  • {name}")

    messages: List[Dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Please triage insurance claim ID: {claim_id}"},
    ]

    cum_prompt = cum_comp = cum_tokens = 0
    cum_cost = 0.0
    laps = 0
    tool_calls_log = []
    termination_reason = "COMPLETED"
    budget_exceeded = None
    final_text = ""
    status = "UNKNOWN"
    payable = 0.0
    active_model = MODEL_NAME

    while True:
        laps += 1
        elapsed = time.time() - start

        if elapsed > max_wall_clock:
            budget_exceeded = "MAX_WALL_CLOCK"
            termination_reason = f"BUDGET: wall-clock {elapsed:.1f}s > {max_wall_clock}s"
            break
        if laps > max_iterations:
            budget_exceeded = "MAX_ITERATIONS"
            termination_reason = f"BUDGET: laps {laps} > {max_iterations}"
            break
        if cum_tokens > max_tokens:
            budget_exceeded = "MAX_TOKENS"
            termination_reason = f"BUDGET: tokens {cum_tokens} > {max_tokens}"
            break
        if cum_cost > max_cost:
            budget_exceeded = "MAX_COST"
            termination_reason = f"BUDGET: cost ${cum_cost:.4f} > ${max_cost:.4f}"
            break

        # ── LLM call ──────────────────────────────────────────────────────────
        resp = None
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=pool.openai_tools,
                    tool_choice="auto",
                    temperature=0.0,
                    max_tokens=1200,
                )
                break
            except Exception as e:
                err = str(e).lower()
                if ("rate_limit" in err or "429" in err) and active_model != FALLBACK_MODEL:
                    active_model = FALLBACK_MODEL
                    time.sleep(0.5)
                elif attempt < 2:
                    time.sleep(2.0)
                else:
                    termination_reason = f"LLM_ERROR: {e}"
                    break

        if resp is None:
            break

        usage = resp.usage
        if usage:
            cum_prompt += usage.prompt_tokens
            cum_comp   += usage.completion_tokens
            cum_tokens += usage.prompt_tokens + usage.completion_tokens
            cum_cost   += (usage.prompt_tokens * INPUT_COST_PER_TOKEN +
                           usage.completion_tokens * OUTPUT_COST_PER_TOKEN)

        msg = resp.choices[0].message
        if msg.content:
            final_text = (final_text + "\n" + msg.content) if final_text else msg.content

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                fn = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}

                if verbose:
                    print(f"  [Lap {laps}] → {fn}({args})")

                # Route to MCP server — zero hardcoding here
                result = pool.call(fn, args)

                tool_calls_log.append({"lap": laps, "tool": fn, "args": args, "result": result})

                # Capture payout info
                if fn == "compute_payout" and result.get("success"):
                    status  = result.get("status", status)
                    payable = result.get("payable_amount", payable)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn,
                    "content": json.dumps(result),
                })
        else:
            if verbose:
                print(f"  [Lap {laps}] Agent finished.")
            break

    total_latency = time.time() - start
    pool.close()

    # Parse status from final text if compute_payout wasn't called
    if status == "UNKNOWN":
        u = final_text.upper()
        if "DENIED" in u:
            status = "DENIED"; payable = 0.0
        elif "COVERED" in u:
            status = "COVERED"

    return {
        "system": "mcp_agent",
        "claim_id": claim_id,
        "status": status,
        "payable_amount": payable,
        "latency_seconds": round(total_latency, 3),
        "total_tokens": cum_tokens,
        "prompt_tokens": cum_prompt,
        "completion_tokens": cum_comp,
        "cost_dollars": round(cum_cost, 6),
        "laps": laps,
        "budget_exceeded": budget_exceeded,
        "termination_reason": termination_reason,
        "tool_calls_made": [t["tool"] for t in tool_calls_log],
        "tool_calls_log": tool_calls_log,
        "final_text": final_text,
        "discovered_tools": pool.tool_names,   # captured before close
    }
