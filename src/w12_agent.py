"""
w12_agent.py — Week 12 Integrated Claims Triage Agent.

Integrates:
  - Week 3-4 RAG pipeline (via MCP server tool discovery)
  - Week 7 hand-built agent loop
  - Week 12 tools: check_coverage_in_force, refer_to_adjuster
  - Per-span tracing with single trace_id across agent and MCP hops
  - PII redaction before any log write
  - Endorsement-version-aware citation format

W12 Compliance rules enforced:
  1. check_coverage_in_force MUST be called before search_policy_exclusions
  2. refer_to_adjuster MUST be the final tool call
  3. Never emit "claim is covered" or "claim is denied" as a verdict
  4. Citation format: [CLAUSE clause_id | ENDORSEMENT endorsement_set | LOSS DATE loss_date]
  5. Deductible, sub_limit, and policy_limit always reported as THREE DISTINCT numbers
"""

import os
import sys
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import MCPClient
from tracer import redact, write_span_trace, PROMPT_VERSION

load_dotenv()

# ---------------------------------------------------------------------------
# Pricing & Defaults
# ---------------------------------------------------------------------------
INPUT_COST_PER_TOKEN  = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012

DEFAULT_MAX_ITERATIONS = 8
DEFAULT_MAX_TOKENS     = 20000
DEFAULT_MAX_COST       = 0.15
DEFAULT_MAX_WALL_CLOCK = 90.0

MODEL_NAME    = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"

MCP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "mcp_config.json")

# ---------------------------------------------------------------------------
# W12 System Prompt — compliance-first, never decides coverage
# ---------------------------------------------------------------------------
W12_SYSTEM_PROMPT = """You are a Claims Triage Assistant. You surface facts and cite policy wording — you do NOT decide coverage.

MANDATORY SEQUENCE for every claim:
1. Call get_claim with the claim_id to load: loss_date, policy_number, form_number, adjuster_notes, claimed_amount, excess_amount.
2. Call check_coverage_in_force with policy_number and loss_date. This determines which endorsement set was in force on the loss date. Use ONLY that endorsement version for all subsequent citations. Never apply current wording to a past loss date.
3. If adjuster notes mention any peril trigger (flood, seepage, mold, earthquake, sinkhole, business pursuits), call search_policy_exclusions with the policy_form and the peril. Your citation MUST name the endorsement version returned in step 2 and the loss date.
4. Report deductible, sub-limit, and policy-limit as THREE DISTINCT numbers from check_coverage_in_force. Never conflate them.
5. Call refer_to_adjuster with the claim_id, your citations (clause + endorsement version + loss date), and the reason for referral. NEVER state that a claim is "covered" or "denied" — always refer to a human adjuster.

Citation format: [CLAUSE clause_id | ENDORSEMENT endorsement_set | LOSS DATE loss_date]
PII: Never include claimant names, addresses, or injury descriptions in your output.
"""


# ---------------------------------------------------------------------------
# MCP Server Pool (identical to mcp_agent.py but with W12 config path)
# ---------------------------------------------------------------------------

def load_mcp_config(config_path: str = MCP_CONFIG_PATH) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


class W12MCPServerPool:
    """
    MCP server pool for W12. Discovers tools at runtime from mcp_config.json.
    Zero hardcoded tool names — adding a new server is config-only.
    """

    def __init__(self, config_path: str = MCP_CONFIG_PATH):
        config = load_mcp_config(config_path)
        servers_cfg = config.get("mcpServers", {})
        self._clients: Dict[str, MCPClient] = {}
        self._tool_to_server: Dict[str, str] = {}
        self._all_tools: List[Dict] = []

        base_dir = os.path.dirname(os.path.abspath(config_path))

        for server_name, srv_cfg in servers_cfg.items():
            cmd = srv_cfg["command"]
            args = srv_cfg.get("args", [])
            cwd = srv_cfg.get("cwd", base_dir)
            if not os.path.isabs(cwd):
                cwd = os.path.join(base_dir, cwd)

            try:
                client = MCPClient(name=server_name, command=cmd, args=args, cwd=cwd)
                client.initialize()
                tools = client.list_tools()

                self._clients[server_name] = client
                for tool in tools:
                    self._tool_to_server[tool["name"]] = server_name
                    self._all_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                        },
                    })
            except Exception as e:
                print(f"  [W12] Warning: could not connect to MCP server '{server_name}': {e}")

    @property
    def openai_tools(self) -> List[Dict]:
        return self._all_tools

    @property
    def tool_names(self) -> List[str]:
        return list(self._tool_to_server.keys())

    def call(self, tool_name: str, arguments: dict) -> dict:
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            # Fallback to local tools module
            try:
                from tools import execute_tool
                return execute_tool(tool_name, arguments)
            except Exception as e:
                return {"success": False, "error": f"Unknown tool '{tool_name}': {e}"}
        return self._clients[server_name].call_tool(tool_name, arguments)

    def close(self) -> None:
        for client in self._clients.values():
            try:
                client.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

def get_groq_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=DEFAULT_MAX_WALL_CLOCK,
    )


# ---------------------------------------------------------------------------
# Main W12 agent runner
# ---------------------------------------------------------------------------

def run_w12_agent(
    claim_id: str,
    config_path: str = MCP_CONFIG_PATH,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_cost: float = DEFAULT_MAX_COST,
    max_wall_clock: float = DEFAULT_MAX_WALL_CLOCK,
    verbose: bool = False,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the W12 integrated triage agent for one claim.

    Returns a structured result with:
      - trace_id (same across all spans — agent + MCP hops)
      - claim_id
      - endorsement_version_applied
      - loss_date
      - deductible, sub_limit, policy_limit (THREE DISTINCT numbers)
      - exclusion_clause_cited (clause + endorsement version)
      - referral_action (always REFER_TO_ADJUSTER)
      - citations
      - final_text
      - cost_per_span, total_cost, total_latency
    """
    # Generate or use provided trace_id — same id propagated to all spans
    tid = trace_id or str(uuid.uuid4())
    if verbose:
        print(f"\n[W12-Agent] trace_id={tid} | claim={claim_id}")

    groq_client = get_groq_client()
    pool = W12MCPServerPool(config_path=config_path)
    start = time.time()

    if verbose:
        print(f"[W12-Agent] Discovered {len(pool.tool_names)} tools: {pool.tool_names}")

    messages: List[Dict] = [
        {"role": "system", "content": W12_SYSTEM_PROMPT},
        {"role": "user", "content": f"Please triage insurance claim ID: {claim_id}"},
    ]

    cum_prompt = cum_comp = cum_tokens = 0
    cum_cost = 0.0
    laps = 0
    tool_calls_log: List[Dict] = []
    termination_reason = "COMPLETED"
    budget_exceeded = None
    final_text = ""
    active_model = MODEL_NAME

    # W12-specific tracking
    endorsement_version_applied: Optional[str] = None
    loss_date_resolved: Optional[str] = None
    deductible: Optional[float] = None
    sub_limit: Optional[float] = None
    policy_limit: Optional[float] = None
    exclusion_clause_cited: Optional[str] = None
    referral_action: Optional[str] = None
    referral_citations: List[str] = []
    cost_per_span: List[Dict] = []

    while True:
        laps += 1
        elapsed = time.time() - start

        # Budget checks
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

        # LLM call with retry/fallback
        lap_start = time.time()
        resp = None
        for attempt in range(3):
            try:
                resp = groq_client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    tools=pool.openai_tools if pool.openai_tools else None,
                    tool_choice="auto" if pool.openai_tools else None,
                    temperature=0.0,
                    max_tokens=1500,
                )
                break
            except Exception as e:
                err = str(e).lower()
                if ("rate_limit" in err or "429" in err) and active_model != FALLBACK_MODEL:
                    if verbose:
                        print(f"  [W12] Rate limit on {active_model}, switching to {FALLBACK_MODEL}")
                    active_model = FALLBACK_MODEL
                    time.sleep(0.5)
                elif attempt < 2:
                    time.sleep(2.0)
                else:
                    termination_reason = f"LLM_ERROR: {e}"
                    break

        if resp is None:
            break

        lap_end = time.time()
        lap_latency_ms = int((lap_end - lap_start) * 1000)

        usage = resp.usage
        lap_prompt_tokens = 0
        lap_comp_tokens = 0
        if usage:
            lap_prompt_tokens = usage.prompt_tokens
            lap_comp_tokens = usage.completion_tokens
            cum_prompt += lap_prompt_tokens
            cum_comp += lap_comp_tokens
            cum_tokens += lap_prompt_tokens + lap_comp_tokens
            lap_cost = (lap_prompt_tokens * INPUT_COST_PER_TOKEN +
                        lap_comp_tokens * OUTPUT_COST_PER_TOKEN)
            cum_cost += lap_cost
        else:
            lap_cost = 0.0

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
                    print(f"  [Lap {laps}] → {fn}({list(args.keys())})")

                tool_start = time.time()
                result = pool.call(fn, args)
                tool_end = time.time()
                tool_latency_ms = int((tool_end - tool_start) * 1000)

                tool_calls_log.append({
                    "lap": laps,
                    "tool": fn,
                    "args": args,
                    "result": result,
                    "latency_ms": tool_latency_ms,
                })

                # Write per-span trace — same trace_id throughout
                write_span_trace(
                    trace_id=tid,
                    span_name=fn,
                    span_start_time=tool_start,
                    span_end_time=tool_end,
                    tokens_in=lap_prompt_tokens,
                    tokens_out=lap_comp_tokens,
                    cost_usd=lap_cost,
                    model=active_model,
                    metadata={
                        "claim_id": redact(claim_id),
                        "tool_args_keys": list(args.keys()),
                        "lap": laps,
                    }
                )
                cost_per_span.append({
                    "span": fn,
                    "latency_ms": tool_latency_ms,
                    "tokens_in": lap_prompt_tokens,
                    "tokens_out": lap_comp_tokens,
                    "cost_usd": round(lap_cost, 7),
                })

                # Extract W12-specific data from tool results
                if fn == "check_coverage_in_force" and result.get("success"):
                    endorsement_version_applied = result.get("endorsement_set")
                    deductible = result.get("deductible")
                    sub_limit = result.get("flood_sublimit")
                    policy_limit = result.get("policy_limit")
                    if verbose:
                        print(f"    endorsement_set={endorsement_version_applied} | "
                              f"deductible={deductible} | sublimit={sub_limit} | limit={policy_limit}")

                elif fn == "get_claim" and result.get("success"):
                    loss_date_resolved = result.get("date_of_loss")

                elif fn == "search_policy_exclusions" and result.get("success"):
                    # Extract first clause citation
                    hits = result.get("results", [])
                    if hits:
                        clause = hits[0].get("clause_id", "")
                        if clause and endorsement_version_applied:
                            exclusion_clause_cited = (
                                f"[CLAUSE {clause} | ENDORSEMENT {endorsement_version_applied} "
                                f"| LOSS DATE {loss_date_resolved}]"
                            )

                elif fn == "refer_to_adjuster" and result.get("success"):
                    referral_action = result.get("action", "REFER_TO_ADJUSTER")
                    referral_citations = result.get("citations", [])
                    if verbose:
                        print(f"    Referral complete: {result.get('message')}")

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

    # Write final LLM generation span
    write_span_trace(
        trace_id=tid,
        span_name="llm_generation_total",
        span_start_time=start,
        span_end_time=start + total_latency,
        tokens_in=cum_prompt,
        tokens_out=cum_comp,
        cost_usd=cum_cost,
        model=active_model,
        metadata={
            "claim_id": redact(claim_id),
            "laps": laps,
            "termination_reason": termination_reason,
            "prompt_version": PROMPT_VERSION,
        }
    )

    return {
        "system": "w12_agent",
        "trace_id": tid,
        "claim_id": claim_id,
        "prompt_version": PROMPT_VERSION,
        # W12-specific fields
        "endorsement_version_applied": endorsement_version_applied,
        "loss_date_resolved": loss_date_resolved,
        "deductible": deductible,
        "sub_limit": sub_limit,
        "policy_limit": policy_limit,
        "exclusion_clause_cited": exclusion_clause_cited,
        "referral_action": referral_action,
        "referral_citations": referral_citations,
        # Execution metrics
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
        "cost_per_span": cost_per_span,
        "final_text": redact(final_text),  # PII redacted before return
        "discovered_tools": pool.tool_names if hasattr(pool, 'tool_names') else [],
    }

