"""
agent.py — Autonomous Claims Triage Agent with Full Budget Enforcement.

Requirements satisfied:
1. Employs the 3 unified tools: get_claim, search_policy_exclusions, compute_payout.
2. Hand-built agent loop with native OpenAI tool calling (using Groq openai/gpt-oss-120b).
3. Enforces all 4 budgets on every single lap:
   - MAX_ITERATIONS
   - MAX_TOKENS (sum of prompt + completion tokens across all laps)
   - MAX_COST (dollar cost computed from cumulative tokens)
   - MAX_WALL_CLOCK_SECONDS (execution time elapsed)
4. Clean termination on budget trigger: stops immediately, logs the triggered budget,
   and outputs a clean structured result rather than spinning or raising unhandled exceptions.
5. Accurately sums per-lap tokens and per-lap costs.
"""

import os
import sys
import time
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(__file__))
from tools import TOOL_DEFINITIONS, execute_tool, ClaimStatus

load_dotenv()

# ---------------------------------------------------------------------------
# Pricing & Defaults
# ---------------------------------------------------------------------------
# Groq OSS / GPT-OSS pricing rates: $0.60 / 1M prompt, $1.20 / 1M completion
INPUT_COST_PER_TOKEN = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012

DEFAULT_MAX_ITERATIONS = 6
DEFAULT_MAX_TOKENS = 12000
DEFAULT_MAX_COST = 0.05
DEFAULT_MAX_WALL_CLOCK = 35.0

MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"
ACTIVE_MODEL = MODEL_NAME

AGENT_SYSTEM_PROMPT = """You are an autonomous Insurance Claims Triage Agent.
Your goal is to triage an incoming insurance claim by following these steps:
1. Call `get_claim` with the claim_id to retrieve the loss date, claimed amount, excess amount, policy form, and adjuster notes.
2. Read the adjuster notes carefully. If a specific peril, cause of loss, or exclusion (e.g. seepage, mold, earthquake, business pursuits) is mentioned, call `search_policy_exclusions` to verify applicable coverage terms or exclusions under the policy form.
3. Determine whether the claim is COVERED, DENIED, or PARTIALLY_COVERED.
4. Call `compute_payout` with the claimed_amount, excess_amount, and determined status ('COVERED', 'DENIED', or 'PARTIALLY_COVERED') to obtain the net payable amount.
5. Finish by providing a clear final summary including:
   - Status: COVERED, DENIED, or PARTIALLY_COVERED
   - Payable Amount: $X.XX
   - Applicable Exclusion: (e.g., E-11, E-31, None)
   - Brief Rationale: why coverage was confirmed or denied

Be direct and use the tools in sequence. Once compute_payout has been executed, output your final summary."""


def get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=DEFAULT_MAX_WALL_CLOCK
    )


def run_claim_agent(
    claim_id: str,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_cost: float = DEFAULT_MAX_COST,
    max_wall_clock: float = DEFAULT_MAX_WALL_CLOCK,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run the autonomous agent loop for a given claim, strictly enforcing all 4 budgets.

    Returns structured dictionary with execution metrics, status, payout, and termination reason.
    """
    client = get_client()
    start_time = time.time()

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Please triage insurance claim ID: {claim_id}"}
    ]

    cum_prompt_tokens = 0
    cum_completion_tokens = 0
    cum_tokens = 0
    cum_cost = 0.0
    laps = 0
    tool_calls_log = []
    budget_exceeded: Optional[str] = None
    termination_reason = "COMPLETED"
    final_text = ""
    status = "UNKNOWN"
    payable_amount = 0.0
    exclusion_code = None

    if verbose:
        print(f"\n[Agent] Starting triage for claim: {claim_id}")

    while True:
        laps += 1
        elapsed = time.time() - start_time

        # ── Budget Check 1: Max Wall Clock ──────────────────────────────────
        if elapsed > max_wall_clock:
            budget_exceeded = "MAX_WALL_CLOCK_SECONDS"
            termination_reason = f"BUDGET EXCEEDED: Wall-clock time ({elapsed:.2f}s) exceeded limit ({max_wall_clock:.2f}s)"
            if verbose:
                print(f"[Agent Budget Termination] {termination_reason}")
            break

        # ── Budget Check 2: Max Iterations ──────────────────────────────────
        if laps > max_iterations:
            budget_exceeded = "MAX_ITERATIONS"
            termination_reason = f"BUDGET EXCEEDED: Iterations ({laps}) exceeded limit ({max_iterations})"
            if verbose:
                print(f"[Agent Budget Termination] {termination_reason}")
            break

        # ── Budget Check 3: Max Tokens ──────────────────────────────────────
        if cum_tokens > max_tokens:
            budget_exceeded = "MAX_TOKENS"
            termination_reason = f"BUDGET EXCEEDED: Cumulative tokens ({cum_tokens}) exceeded limit ({max_tokens})"
            if verbose:
                print(f"[Agent Budget Termination] {termination_reason}")
            break

        # ── Budget Check 4: Max Cost ────────────────────────────────────────
        if cum_cost > max_cost:
            budget_exceeded = "MAX_COST"
            termination_reason = f"BUDGET EXCEEDED: Cumulative cost (${cum_cost:.4f}) exceeded limit (${max_cost:.4f})"
            if verbose:
                print(f"[Agent Budget Termination] {termination_reason}")
            break

        # LLM Call with Rate Limit Fallback
        global ACTIVE_MODEL
        response = None
        for call_attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=ACTIVE_MODEL,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.0,
                    max_tokens=1000
                )
                break
            except Exception as e:
                err_str = str(e).lower()
                if ("rate_limit" in err_str or "429" in err_str) and ACTIVE_MODEL != FALLBACK_MODEL:
                    if verbose:
                        print(f"  [Agent RateLimit] {ACTIVE_MODEL} limited. Retrying with {FALLBACK_MODEL}...")
                    ACTIVE_MODEL = FALLBACK_MODEL
                    time.sleep(0.5)
                    continue
                elif call_attempt < 2:
                    time.sleep(2.0)
                else:
                    termination_reason = f"LLM_CALL_ERROR: {str(e)}"
                    if verbose:
                        print(f"[Agent Error] {termination_reason}")
                    break

        if not response:
            break

        # Record tokens and cost for this lap
        usage = response.usage
        if usage:
            lap_prompt = usage.prompt_tokens
            lap_comp = usage.completion_tokens
            cum_prompt_tokens += lap_prompt
            cum_completion_tokens += lap_comp
            cum_tokens += (lap_prompt + lap_comp)
            cum_cost += (lap_prompt * INPUT_COST_PER_TOKEN) + (lap_comp * OUTPUT_COST_PER_TOKEN)

        choice = response.choices[0]
        message = choice.message

        # Check post-call tokens & cost budgets immediately
        if cum_tokens > max_tokens:
            budget_exceeded = "MAX_TOKENS"
            termination_reason = f"BUDGET EXCEEDED: Cumulative tokens ({cum_tokens}) exceeded limit ({max_tokens})"
            break
        if cum_cost > max_cost:
            budget_exceeded = "MAX_COST"
            termination_reason = f"BUDGET EXCEEDED: Cumulative cost (${cum_cost:.4f}) exceeded limit (${max_cost:.4f})"
            break

        # If LLM returned text
        if message.content:
            final_text += ("\n" + message.content) if final_text else message.content

        # Handle tool calls
        if message.tool_calls:
            # Append assistant message with tool calls to context
            messages.append(message)

            for tc in message.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except Exception:
                    fn_args = {}

                if verbose:
                    print(f"  [Lap {laps}] Tool call -> {fn_name}({fn_args})")

                tool_result = execute_tool(fn_name, fn_args)
                tool_calls_log.append({
                    "lap": laps,
                    "tool": fn_name,
                    "args": fn_args,
                    "result": tool_result
                })

                # If compute_payout was executed, capture its payout and status
                if fn_name == "compute_payout" and tool_result.get("success"):
                    status = tool_result.get("status", status)
                    payable_amount = tool_result.get("payable_amount", payable_amount)

                # Feed tool response back into message history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": json.dumps(tool_result)
                })
        else:
            # No tool calls: model completed its reasoning and provided final response
            if verbose:
                print(f"  [Lap {laps}] Agent finished triage response.")
            break

    total_latency = time.time() - start_time

    # If status wasn't set by compute_payout, parse from final_text or tools
    if status == "UNKNOWN":
        upper_final = final_text.upper()
        if "DENIED" in upper_final or "EXCLUSION" in upper_final:
            status = "DENIED"
            payable_amount = 0.0
        elif "COVERED" in upper_final:
            status = "COVERED"

    # Extract exclusion code if mentioned
    for code in ["E-11", "E-19", "E-22", "E-31", "E-33"]:
        if code in final_text:
            exclusion_code = code
            break

    return {
        "system": "agent",
        "claim_id": claim_id,
        "status": status,
        "payable_amount": payable_amount,
        "exclusion_code": exclusion_code,
        "latency_seconds": round(total_latency, 3),
        "total_tokens": cum_tokens,
        "prompt_tokens": cum_prompt_tokens,
        "completion_tokens": cum_completion_tokens,
        "cost_dollars": round(cum_cost, 6),
        "laps": laps,
        "budget_exceeded": budget_exceeded,
        "termination_reason": termination_reason,
        "tool_calls_made": [t["tool"] for t in tool_calls_log],
        "tool_calls_log": tool_calls_log,
        "final_text": final_text
    }
