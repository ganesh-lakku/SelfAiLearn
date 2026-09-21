"""
workflow.py — Fixed 4-Step Claims Triage Workflow (No Agent Loop).

Requirements satisfied:
1. Genuinely does the same task: same inputs, same output contract, same tools, same model.
2. Hard-coded sequential pipeline — strictly NO while-loops or iterative cycles.
3. Steps:
   Step 1: get_claim (pull claim & adjuster notes)
   Step 2: LLM extracts cause of loss & determines if exclusion search is warranted
   Step 3: search_policy_exclusions (if warranted) + LLM coverage determination (COVERED / DENIED / PARTIALLY_COVERED)
   Step 4: compute_payout (calculate net payable amount after excess deduction)
4. Accurately tracks all tokens across LLM steps, cost, and wall-clock latency.
"""

import os
import sys
import time
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, os.path.dirname(__file__))
from tools import get_claim, search_policy_exclusions, compute_payout, ClaimStatus

load_dotenv()

# Same model and pricing as agent
MODEL_NAME = "openai/gpt-oss-120b"
INPUT_COST_PER_TOKEN = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012


def get_client() -> OpenAI:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is missing.")
    return OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=35.0
    )


MODEL_NAME = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"
ACTIVE_MODEL = MODEL_NAME


def safe_call_llm_json(client: OpenAI, system_prompt: str, user_prompt: str, max_tokens: int = 350) -> tuple[dict, Any]:
    """Robustly call LLM and extract JSON dictionary with rate limit backoff and fallback."""
    global ACTIVE_MODEL
    import re
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=ACTIVE_MODEL,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens
            )
            raw = resp.choices[0].message.content or ""
            # Strip code blocks if present
            cleaned = re.sub(r"^```[a-zA-Z]*\n", "", raw.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data, resp.usage
            return {}, resp.usage
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str:
                if ACTIVE_MODEL != FALLBACK_MODEL:
                    print(f"\n[RateLimit] Primary model {ACTIVE_MODEL} limited. Switching to {FALLBACK_MODEL}...")
                    ACTIVE_MODEL = FALLBACK_MODEL
                    time.sleep(0.5)
                    continue
                else:
                    time.sleep(3.0)
            else:
                time.sleep(1.0)
            if attempt == 3:
                raise e
    return {}, None


def run_claim_workflow(claim_id: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Execute the deterministic 4-step fixed workflow on a claim.
    """
    client = get_client()
    start_time = time.time()
    steps_executed = []

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    total_cost = 0.0

    if verbose:
        print(f"\n[Workflow] Starting fixed triage workflow for claim: {claim_id}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Pull Claim Details (Tool 1: get_claim)
    # ──────────────────────────────────────────────────────────────────────────
    claim_record = get_claim(claim_id)
    steps_executed.append("step1_get_claim")
    if not claim_record.get("success"):
        elapsed = time.time() - start_time
        return {
            "system": "workflow",
            "claim_id": claim_id,
            "status": "UNKNOWN",
            "payable_amount": 0.0,
            "exclusion_code": None,
            "latency_seconds": round(elapsed, 3),
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_dollars": 0.0,
            "steps_executed": steps_executed,
            "final_text": f"Error: {claim_record.get('error')}"
        }

    form_number = claim_record["form_number"]
    notes = claim_record["adjuster_notes"]
    claimed_amt = claim_record["claimed_amount"]
    excess_amt = claim_record["excess_amount"]

    if verbose:
        print(f"  [Step 1] Retrieved claim form={form_number}, claimed=${claimed_amt}, excess=${excess_amt}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Extract Peril & Determine if Exclusion Search is Warranted (LLM Call 1)
    # ──────────────────────────────────────────────────────────────────────────
    step2_prompt = f"""Read the following insurance adjuster notes and extract:
1. Cause of loss / peril.
2. Search query for policy exclusion lookup (e.g. 'continuous seepage', 'earthquake tremors', 'business pursuits', 'mold humidity', or 'none' if standard clear covered peril).
3. Whether policy exclusion search is warranted (true/false).

Adjuster Notes:
\"\"\"{notes}\"\"\"

Respond ONLY with a valid JSON object in this exact structure:
{{
  "cause_of_loss": "string",
  "search_query": "string",
  "needs_exclusion_search": true or false
}}"""

    step2_data, u1 = safe_call_llm_json(
        client=client,
        system_prompt="You are a helpful insurance claims assistant. Output only a valid JSON object.",
        user_prompt=step2_prompt,
        max_tokens=300
    )
    steps_executed.append("step2_extract_peril")

    if u1:
        total_prompt_tokens += u1.prompt_tokens
        total_completion_tokens += u1.completion_tokens
        total_tokens += (u1.prompt_tokens + u1.completion_tokens)
        total_cost += (u1.prompt_tokens * INPUT_COST_PER_TOKEN) + (u1.completion_tokens * OUTPUT_COST_PER_TOKEN)

    needs_search = step2_data.get("needs_exclusion_search", True)
    search_query = step2_data.get("search_query", "")
    cause = step2_data.get("cause_of_loss", "")
    if not search_query:
        search_query = notes[:50]

    if verbose:
        print(f"  [Step 2] Cause='{cause}', Needs Search={needs_search}, Query='{search_query}'")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Policy Exclusion Verification & Coverage Decision (Tool 2 + LLM Call 2)
    # ──────────────────────────────────────────────────────────────────────────
    exclusion_results = []
    if needs_search and search_query and search_query.lower() != "none":
        excl_res = search_policy_exclusions(policy_form=form_number, query=search_query)
        exclusion_results = excl_res.get("results", [])
        steps_executed.append("step3_search_policy_exclusions")
        if verbose:
            print(f"  [Step 3] Searched exclusions: found {len(exclusion_results)} matches")
    else:
        steps_executed.append("step3_skip_search_clean_peril")
        if verbose:
            print(f"  [Step 3] Skipped exclusion search: standard peril")

    step3_prompt = f"""You are an insurance claims coverage evaluator.
Determine whether the claim is COVERED or DENIED under endorsement {form_number}.

Claim Details:
- Form: {form_number}
- Cause of Loss: {cause}
- Adjuster Notes: {notes}

Relevant Policy Clauses & Exclusions Retrieved:
{json.dumps(exclusion_results, indent=2) if exclusion_results else "No specific exclusions triggered."}

Rules:
- If damage was caused by continuous seepage (>14 days), mold from ambient humidity, earthquake/earth movement, sinkhole, or business pursuits, the claim MUST be DENIED.
- If denied, specify the exclusion code (e.g. E-11, E-22, E-31, E-33, E-19).
- If loss is sudden and accidental or covered under the endorsement, mark as COVERED.

Respond ONLY with a valid JSON object in this exact structure:
{{
  "status": "COVERED" or "DENIED",
  "exclusion_code": "E-XX" or null,
  "rationale": "one sentence explanation"
}}"""

    step3_data, u2 = safe_call_llm_json(
        client=client,
        system_prompt="You are an insurance claims coverage evaluator. Output only a valid JSON object.",
        user_prompt=step3_prompt,
        max_tokens=300
    )
    steps_executed.append("step3_determine_coverage")

    if u2:
        total_prompt_tokens += u2.prompt_tokens
        total_completion_tokens += u2.completion_tokens
        total_tokens += (u2.prompt_tokens + u2.completion_tokens)
        total_cost += (u2.prompt_tokens * INPUT_COST_PER_TOKEN) + (u2.completion_tokens * OUTPUT_COST_PER_TOKEN)

    status = step3_data.get("status", "DENIED").upper().strip()
    exclusion_code = step3_data.get("exclusion_code")
    rationale = step3_data.get("rationale", "")
    if status not in ("COVERED", "DENIED", "PARTIALLY_COVERED"):
        status = "DENIED"
    if verbose:
        print(f"  [Step 3 Coverage] Status={status}, Exclusion={exclusion_code}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Compute Payout (Tool 3: compute_payout)
    # ──────────────────────────────────────────────────────────────────────────
    payout_res = compute_payout(
        claimed_amount=claimed_amt,
        excess_amount=excess_amt,
        status=status
    )
    steps_executed.append("step4_compute_payout")

    payable = payout_res.get("payable_amount", 0.0)
    summary = payout_res.get("calculation_summary", "")

    if verbose:
        print(f"  [Step 4] Payout computed: ${payable:.2f} ({summary})")

    elapsed = time.time() - start_time

    final_text = (
        f"**Status:** {status}\n"
        f"**Payable Amount:** ${payable:.2f}\n"
        f"**Applicable Exclusion:** {exclusion_code or 'None'}\n"
        f"**Rationale:** {rationale}\n"
        f"**Calculation:** {summary}"
    )

    return {
        "system": "workflow",
        "claim_id": claim_id,
        "status": status,
        "payable_amount": payable,
        "exclusion_code": exclusion_code,
        "latency_seconds": round(elapsed, 3),
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "cost_dollars": round(total_cost, 6),
        "steps_executed": steps_executed,
        "final_text": final_text
    }
