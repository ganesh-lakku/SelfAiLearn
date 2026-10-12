"""
orchestrator.py — Week 10 Multi-Agent Orchestrator for Claims Triage.

Architecture:
  - Orchestrator decomposes the claim question into two parallel worker tasks.
  - Worker A (coverage_worker): narrow-scoped, reads claim + searches exclusions only.
    Tools: get_claim, search_policy_exclusions  (NO compute_payout)
  - Worker B (adjuster_summary_worker): reads adjuster notes and returns a structured
    cause-of-loss summary only.
    Tools: get_claim only (narrower prompt, no coverage decision)
  - Orchestrator synthesises both worker outputs into the final coverage decision
    and calls compute_payout.

Hand-off log is emitted for every A2A message so token counts per hop are visible.

Failure injection:
  Set inject_failure_on_claim_id="CLM-2024-XXXXX" to make the coverage worker
  simulate a 500 on that specific claim. The orchestrator will detect the failure
  and record its actual behaviour (retry / degrade / lie).
"""

import os
import sys
import json
import time
import re
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(__file__))
from tools import get_claim, search_policy_exclusions, compute_payout

load_dotenv()

# ── Pricing (identical to single agent) ──────────────────────────────────────
INPUT_COST_PER_TOKEN  = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012

MODEL_NAME    = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"

# ── Handoff log (module-level, cleared per run) ───────────────────────────────
_HANDOFF_LOG: List[Dict[str, Any]] = []


def _log_handoff(
    from_agent: str,
    to_agent: str,
    direction: str,
    payload_tokens: int,
    payload_summary: str,
    claim_id: str,
) -> None:
    """Record one A2A hand-off with its token cost."""
    entry = {
        "timestamp": time.time(),
        "claim_id": claim_id,
        "from": from_agent,
        "to": to_agent,
        "direction": direction,
        "payload_tokens": payload_tokens,
        "payload_summary": payload_summary,
    }
    _HANDOFF_LOG.append(entry)


def get_handoff_log() -> List[Dict[str, Any]]:
    return list(_HANDOFF_LOG)


def clear_handoff_log() -> None:
    _HANDOFF_LOG.clear()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


# ── LLM client helper ─────────────────────────────────────────────────────────

def _get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=60.0,
    )


def _call_llm(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 400,
    active_model: Optional[str] = None,
) -> Tuple[str, Any, str]:
    """
    Single LLM call with rate-limit fallback.
    Returns (text_response, usage_object, model_used).
    """
    model = active_model or MODEL_NAME
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or "", resp.usage, model
        except Exception as e:
            err = str(e).lower()
            if ("rate_limit" in err or "429" in err) and model != FALLBACK_MODEL:
                model = FALLBACK_MODEL
                time.sleep(0.5)
                continue
            elif attempt < 3:
                time.sleep(2.0)
            else:
                raise


def _parse_json_from_text(text: str) -> dict:
    """Extract JSON object from LLM response text."""
    cleaned = re.sub(r"^```[a-zA-Z]*\n", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Worker A: Coverage / Exclusions Worker
# Narrow scope: reads claim + searches exclusions → returns coverage decision
# Tools: get_claim, search_policy_exclusions  (NOT compute_payout)
# ─────────────────────────────────────────────────────────────────────────────

COVERAGE_WORKER_SYSTEM = """You are a Coverage & Exclusions specialist agent.
Your ONLY job is to determine whether a claim is covered or excluded under the policy.

Steps:
1. Read the claim record provided.
2. Identify any perils that need exclusion verification (seepage, mold, earthquake,
   sinkhole, business pursuits, etc.).
3. Examine the policy exclusion search results provided.
4. Return a JSON coverage decision with: status, exclusion_code, rationale.

You do NOT compute payouts. You do NOT summarise adjuster notes. Coverage decision ONLY.

Output ONLY valid JSON:
{
  "status": "COVERED" | "DENIED" | "PARTIALLY_COVERED",
  "exclusion_code": "E-XX" or null,
  "rationale": "one concise sentence",
  "needs_exclusion_search": true | false,
  "peril_query": "short search phrase or null"
}"""


def run_coverage_worker(
    claim_id: str,
    inject_500: bool = False,
) -> Dict[str, Any]:
    """
    Worker A: Coverage & Exclusions decision.
    Returns structured result with token usage.
    inject_500=True simulates a server 500 on this claim.
    """
    if inject_500:
        return {
            "worker": "coverage_worker",
            "claim_id": claim_id,
            "success": False,
            "error": "HTTP 500 Internal Server Error — coverage worker unavailable",
            "status": None,
            "exclusion_code": None,
            "rationale": None,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_dollars": 0.0,
            "latency_seconds": 0.0,
        }

    client = _get_client()
    start = time.time()
    total_prompt = total_comp = total_tokens = 0
    total_cost = 0.0

    # Step 1: fetch claim (deterministic tool, no LLM tokens)
    claim_rec = get_claim(claim_id)
    if not claim_rec.get("success"):
        return {
            "worker": "coverage_worker",
            "claim_id": claim_id,
            "success": False,
            "error": claim_rec.get("error", "Unknown claim error"),
            "total_tokens": 0,
            "cost_dollars": 0.0,
            "latency_seconds": round(time.time() - start, 3),
        }

    form    = claim_rec["form_number"]
    notes   = claim_rec["adjuster_notes"]
    claimed = claim_rec["claimed_amount"]
    excess  = claim_rec["excess_amount"]

    # Step 2: LLM call — determine whether exclusion search is needed + make
    #         preliminary coverage decision based on notes alone
    user_prompt = f"""Claim ID: {claim_id}
Policy Form: {form}
Adjuster Notes:
\"\"\"{notes}\"\"\"

Determine coverage. If the notes mention any exclusion trigger (seepage >14 days,
mold from humidity, earthquake, sinkhole, business pursuits) set needs_exclusion_search=true.
Return JSON."""

    raw, usage, _ = _call_llm(
        client, COVERAGE_WORKER_SYSTEM, user_prompt, max_tokens=300
    )
    if usage:
        total_prompt += usage.prompt_tokens
        total_comp   += usage.completion_tokens
        total_tokens += usage.prompt_tokens + usage.completion_tokens
        total_cost   += (usage.prompt_tokens * INPUT_COST_PER_TOKEN +
                         usage.completion_tokens * OUTPUT_COST_PER_TOKEN)

    parsed = _parse_json_from_text(raw)
    needs_search = parsed.get("needs_exclusion_search", True)
    peril_query  = parsed.get("peril_query", "") or ""

    # Step 3: Run exclusion search if warranted (deterministic, no LLM)
    excl_results = []
    if needs_search and peril_query and peril_query.lower() != "null":
        excl_res     = search_policy_exclusions(form, peril_query)
        excl_results = excl_res.get("results", [])

    # Step 4: Final LLM call — coverage decision with exclusion evidence
    final_prompt = f"""Claim: {claim_id} | Form: {form}
Notes: {notes}

Exclusion search results:
{json.dumps(excl_results, indent=2) if excl_results else "No specific exclusions found."}

Final coverage decision (JSON only):"""

    raw2, usage2, _ = _call_llm(
        client, COVERAGE_WORKER_SYSTEM, final_prompt, max_tokens=300
    )
    if usage2:
        total_prompt += usage2.prompt_tokens
        total_comp   += usage2.completion_tokens
        total_tokens += usage2.prompt_tokens + usage2.completion_tokens
        total_cost   += (usage2.prompt_tokens * INPUT_COST_PER_TOKEN +
                         usage2.completion_tokens * OUTPUT_COST_PER_TOKEN)

    parsed2 = _parse_json_from_text(raw2)
    status  = parsed2.get("status", "DENIED").upper().strip()
    excl_code = parsed2.get("exclusion_code")
    rationale = parsed2.get("rationale", "")
    if status not in ("COVERED", "DENIED", "PARTIALLY_COVERED"):
        status = "DENIED"

    return {
        "worker": "coverage_worker",
        "claim_id": claim_id,
        "success": True,
        "status": status,
        "exclusion_code": excl_code,
        "rationale": rationale,
        "claimed_amount": claimed,
        "excess_amount": excess,
        "form_number": form,
        "excl_results_count": len(excl_results),
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_comp,
        "cost_dollars": round(total_cost, 6),
        "latency_seconds": round(time.time() - start, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Worker B: Adjuster-Note Summary Worker
# Narrow scope: reads claim → returns structured cause-of-loss summary only
# Tools: get_claim (read only)
# ─────────────────────────────────────────────────────────────────────────────

SUMMARY_WORKER_SYSTEM = """You are an Adjuster Note Summariser agent.
Your ONLY job is to extract a structured cause-of-loss summary from adjuster notes.

You do NOT make coverage decisions. You do NOT search exclusions. Summary ONLY.

Output ONLY valid JSON:
{
  "cause_of_loss": "brief description",
  "peril_type": "water | mold | earth_movement | theft | business_liability | other",
  "dynamic_dependency": true | false,
  "key_facts": ["fact 1", "fact 2"],
  "exclusion_trigger": "specific trigger phrase or null"
}"""


def run_adjuster_summary_worker(claim_id: str) -> Dict[str, Any]:
    """
    Worker B: Adjuster note summariser.
    Returns structured cause-of-loss summary with token usage.
    """
    client = _get_client()
    start  = time.time()

    # Fetch claim (deterministic, no LLM tokens)
    claim_rec = get_claim(claim_id)
    if not claim_rec.get("success"):
        return {
            "worker": "adjuster_summary_worker",
            "claim_id": claim_id,
            "success": False,
            "error": claim_rec.get("error", "Unknown claim error"),
            "total_tokens": 0,
            "cost_dollars": 0.0,
            "latency_seconds": round(time.time() - start, 3),
        }

    notes = claim_rec["adjuster_notes"]
    form  = claim_rec["form_number"]

    user_prompt = f"""Policy Form: {form}
Adjuster Notes:
\"\"\"{notes}\"\"\"

Extract structured cause-of-loss summary. Output JSON only."""

    raw, usage, _ = _call_llm(
        client, SUMMARY_WORKER_SYSTEM, user_prompt, max_tokens=250
    )

    total_prompt = usage.prompt_tokens if usage else 0
    total_comp   = usage.completion_tokens if usage else 0
    total_tokens = total_prompt + total_comp
    total_cost   = (total_prompt * INPUT_COST_PER_TOKEN +
                    total_comp * OUTPUT_COST_PER_TOKEN) if usage else 0.0

    parsed = _parse_json_from_text(raw)

    return {
        "worker": "adjuster_summary_worker",
        "claim_id": claim_id,
        "success": True,
        "cause_of_loss":    parsed.get("cause_of_loss", ""),
        "peril_type":       parsed.get("peril_type", ""),
        "dynamic_dependency": parsed.get("dynamic_dependency", False),
        "key_facts":        parsed.get("key_facts", []),
        "exclusion_trigger": parsed.get("exclusion_trigger"),
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_comp,
        "cost_dollars": round(total_cost, 6),
        "latency_seconds": round(time.time() - start, 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator — synthesises workers + calls compute_payout
# ─────────────────────────────────────────────────────────────────────────────

ORCHESTRATOR_SYSTEM = """You are an Insurance Claims Orchestrator.
You receive outputs from two specialist workers:
  - Coverage Worker: coverage decision (COVERED/DENIED/PARTIALLY_COVERED) + exclusion code
  - Adjuster Summary Worker: cause-of-loss structured summary

Your job: synthesise both outputs into the final authoritative coverage decision.
IMPORTANT: Do NOT upgrade "DENIED" to "COVERED" without explicit coverage evidence.
If the coverage worker failed (500 error), you must note this and use the summary
worker's output cautiously — do NOT declare covered without exclusion check.

Output ONLY valid JSON:
{
  "status": "COVERED" | "DENIED" | "PARTIALLY_COVERED",
  "exclusion_code": "E-XX" or null,
  "rationale": "one concise sentence",
  "coverage_worker_used": true | false,
  "degraded_mode": true | false
}"""


def run_orchestrator(
    claim_id: str,
    inject_failure_on_claim_id: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Run the full multi-agent orchestrator for one claim.
    
    Args:
        claim_id: The claim to triage.
        inject_failure_on_claim_id: If equals claim_id, injects a 500 into the
            coverage worker to test failure handling.
        verbose: Print progress to stdout.
    
    Returns:
        Structured result matching single-agent output contract plus handoff_log.
    """
    clear_handoff_log()
    client  = _get_client()
    start   = time.time()
    total_prompt = total_comp = total_tokens = 0
    total_cost = 0.0
    failure_injected = (inject_failure_on_claim_id == claim_id)

    if verbose:
        print(f"\n[Orchestrator] Triaging claim: {claim_id}")
        if failure_injected:
            print(f"  [!] FAILURE INJECTION: coverage worker will return 500 on {claim_id}")

    # ── Hand-off 1: Orchestrator → Coverage Worker ────────────────────────────
    task_payload   = json.dumps({"claim_id": claim_id, "task": "coverage_decision"})
    task_tok       = _estimate_tokens(task_payload)
    _log_handoff(
        from_agent="orchestrator",
        to_agent="coverage_worker",
        direction="request",
        payload_tokens=task_tok,
        payload_summary=f"Request coverage decision for {claim_id}",
        claim_id=claim_id,
    )

    coverage_result = run_coverage_worker(claim_id, inject_500=failure_injected)
    coverage_worker_succeeded = coverage_result.get("success", False)

    # ── Hand-off 2: Coverage Worker → Orchestrator ────────────────────────────
    cov_payload = json.dumps(coverage_result)
    cov_tok     = _estimate_tokens(cov_payload)
    _log_handoff(
        from_agent="coverage_worker",
        to_agent="orchestrator",
        direction="response",
        payload_tokens=cov_tok,
        payload_summary=(
            f"Coverage={coverage_result.get('status')} "
            f"Excl={coverage_result.get('exclusion_code')} "
            f"tokens={coverage_result.get('total_tokens',0)}"
            if coverage_worker_succeeded
            else f"ERROR: {coverage_result.get('error','500')}"
        ),
        claim_id=claim_id,
    )

    if coverage_worker_succeeded:
        total_prompt += coverage_result.get("prompt_tokens", 0)
        total_comp   += coverage_result.get("completion_tokens", 0)
        total_tokens += coverage_result.get("total_tokens", 0)
        total_cost   += coverage_result.get("cost_dollars", 0.0)

    # ── Hand-off 3: Orchestrator → Adjuster Summary Worker ───────────────────
    summ_payload = json.dumps({"claim_id": claim_id, "task": "adjuster_note_summary"})
    summ_req_tok = _estimate_tokens(summ_payload)
    _log_handoff(
        from_agent="orchestrator",
        to_agent="adjuster_summary_worker",
        direction="request",
        payload_tokens=summ_req_tok,
        payload_summary=f"Request adjuster note summary for {claim_id}",
        claim_id=claim_id,
    )

    summary_result = run_adjuster_summary_worker(claim_id)
    summary_worker_succeeded = summary_result.get("success", False)

    # ── Hand-off 4: Adjuster Summary Worker → Orchestrator ───────────────────
    summ_resp_payload = json.dumps(summary_result)
    summ_resp_tok     = _estimate_tokens(summ_resp_payload)
    _log_handoff(
        from_agent="adjuster_summary_worker",
        to_agent="orchestrator",
        direction="response",
        payload_tokens=summ_resp_tok,
        payload_summary=(
            f"CauseOfLoss='{summary_result.get('cause_of_loss','')}' "
            f"Trigger='{summary_result.get('exclusion_trigger','')}' "
            f"tokens={summary_result.get('total_tokens',0)}"
        ),
        claim_id=claim_id,
    )

    if summary_worker_succeeded:
        total_prompt += summary_result.get("prompt_tokens", 0)
        total_comp   += summary_result.get("completion_tokens", 0)
        total_tokens += summary_result.get("total_tokens", 0)
        total_cost   += summary_result.get("cost_dollars", 0.0)

    if verbose:
        print(f"  [Coverage Worker] success={coverage_worker_succeeded} "
              f"tokens={coverage_result.get('total_tokens',0)}")
        print(f"  [Summary Worker]  success={summary_worker_succeeded} "
              f"tokens={summary_result.get('total_tokens',0)}")

    # ── Orchestrator synthesis LLM call ──────────────────────────────────────
    synth_input = {
        "claim_id": claim_id,
        "coverage_worker_result": (
            {
                "status":         coverage_result.get("status"),
                "exclusion_code": coverage_result.get("exclusion_code"),
                "rationale":      coverage_result.get("rationale"),
            }
            if coverage_worker_succeeded
            else {"error": coverage_result.get("error"), "status": None}
        ),
        "adjuster_summary_result": (
            {
                "cause_of_loss":    summary_result.get("cause_of_loss"),
                "peril_type":       summary_result.get("peril_type"),
                "dynamic_dependency": summary_result.get("dynamic_dependency"),
                "exclusion_trigger": summary_result.get("exclusion_trigger"),
            }
            if summary_worker_succeeded
            else {"error": summary_result.get("error")}
        ),
        "coverage_worker_failed": not coverage_worker_succeeded,
    }

    synth_user_prompt = f"""Synthesise these worker outputs into a final coverage decision:

{json.dumps(synth_input, indent=2)}

{"IMPORTANT: The coverage worker FAILED with a 500 error. You only have the adjuster summary. " 
 "Do NOT declare covered without exclusion verification. Use 'degraded_mode: true'." 
 if not coverage_worker_succeeded else ""}

Output JSON only."""

    # Log the re-send payload (context re-send to synthesis)
    synth_payload_text = ORCHESTRATOR_SYSTEM + synth_user_prompt
    synth_resend_tok   = _estimate_tokens(synth_payload_text)
    _log_handoff(
        from_agent="orchestrator",
        to_agent="orchestrator_synthesis_llm",
        direction="synthesis_request",
        payload_tokens=synth_resend_tok,
        payload_summary="Orchestrator synthesises worker outputs; re-sends both payloads to LLM",
        claim_id=claim_id,
    )

    raw_synth, usage_synth, _ = _call_llm(
        client,
        ORCHESTRATOR_SYSTEM,
        synth_user_prompt,
        max_tokens=300,
    )

    if usage_synth:
        total_prompt += usage_synth.prompt_tokens
        total_comp   += usage_synth.completion_tokens
        total_tokens += usage_synth.prompt_tokens + usage_synth.completion_tokens
        total_cost   += (usage_synth.prompt_tokens * INPUT_COST_PER_TOKEN +
                         usage_synth.completion_tokens * OUTPUT_COST_PER_TOKEN)

    synth_parsed = _parse_json_from_text(raw_synth)

    status       = synth_parsed.get("status", "DENIED").upper().strip()
    excl_code    = synth_parsed.get("exclusion_code")
    rationale    = synth_parsed.get("rationale", "")
    degraded     = synth_parsed.get("degraded_mode", not coverage_worker_succeeded)

    if status not in ("COVERED", "DENIED", "PARTIALLY_COVERED"):
        status = "DENIED"

    # Log synthesis response
    synth_resp_tok = _estimate_tokens(raw_synth)
    _log_handoff(
        from_agent="orchestrator_synthesis_llm",
        to_agent="orchestrator",
        direction="synthesis_response",
        payload_tokens=synth_resp_tok,
        payload_summary=f"Final decision: status={status} excl={excl_code} degraded={degraded}",
        claim_id=claim_id,
    )

    # ── Compute payout (deterministic) ───────────────────────────────────────
    # Get claim amounts (from coverage worker if available, else fetch fresh)
    claimed_amt = coverage_result.get("claimed_amount")
    excess_amt  = coverage_result.get("excess_amount")
    if claimed_amt is None:
        fresh = get_claim(claim_id)
        claimed_amt = fresh.get("claimed_amount", 0.0)
        excess_amt  = fresh.get("excess_amount", 0.0)

    payout_res = compute_payout(
        claimed_amount=float(claimed_amt),
        excess_amount=float(excess_amt),
        status=status,
    )
    payable = payout_res.get("payable_amount", 0.0)

    # Final hand-off log entry
    _log_handoff(
        from_agent="orchestrator",
        to_agent="caller",
        direction="final_result",
        payload_tokens=_estimate_tokens(json.dumps({"status": status, "payable": payable})),
        payload_summary=f"Final: status={status} payable=${payable:.2f} degraded={degraded}",
        claim_id=claim_id,
    )

    total_latency = time.time() - start

    final_text = (
        f"**Status:** {status}\n"
        f"**Payable Amount:** ${payable:.2f}\n"
        f"**Applicable Exclusion:** {excl_code or 'None'}\n"
        f"**Rationale:** {rationale}\n"
        f"**Degraded Mode:** {degraded} (coverage worker failed={not coverage_worker_succeeded})"
    )

    if verbose:
        print(f"  [Orchestrator] Final: status={status} payable=${payable:.2f} "
              f"tokens={total_tokens} degraded={degraded}")

    return {
        "system": "orchestrator",
        "claim_id": claim_id,
        "status": status,
        "payable_amount": payable,
        "exclusion_code": excl_code,
        "latency_seconds": round(total_latency, 3),
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt,
        "completion_tokens": total_comp,
        "cost_dollars": round(total_cost, 6),
        "degraded_mode": degraded,
        "coverage_worker_succeeded": coverage_worker_succeeded,
        "failure_injected": failure_injected,
        "handoff_log": get_handoff_log(),
        "termination_reason": "COMPLETED",
        "budget_exceeded": None,
        "final_text": final_text,
    }
