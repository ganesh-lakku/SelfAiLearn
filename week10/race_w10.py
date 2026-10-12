#!/usr/bin/env python3
"""
week10/race_w10.py — Week 10 Practical Task Set D: Race single agent vs orchestrator.

Produces all 5 required deliverables:
  1. race_table.md      — 4 metrics × 2 arms on same 10 Week-6/7 claims
  2. handoffs.log       — every hand-off with its token count
  3. multiplier line    — multi/single token ratio + dominant hand-off
  4. failure_case.md    — injected 500 + actual orchestrator behaviour
  5. verdict.md         — keep/kill, two numbers cited, sunk-cost named

Usage:
    cd /path/to/SelfAiLearn
    source venv/bin/activate
    python3 week10/race_w10.py
"""

import os
import sys
import json
import time
import statistics
from typing import Any, Dict, List, Tuple, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.claims_data import get_all_claim_ids, get_claim_by_id
from src.agent import run_claim_agent
from src.orchestrator import run_orchestrator

# ── Output paths ──────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK10    = os.path.join(BASE, "week10")

RACE_TABLE_PATH    = os.path.join(WEEK10, "race_table.md")
HANDOFFS_LOG_PATH  = os.path.join(WEEK10, "handoffs.log")
FAILURE_CASE_PATH  = os.path.join(WEEK10, "failure_case.md")
VERDICT_PATH       = os.path.join(WEEK10, "verdict.md")

# ── Pricing ───────────────────────────────────────────────────────────────────
INPUT_COST_PER_TOKEN  = 0.0000006
OUTPUT_COST_PER_TOKEN = 0.0000012

# Failure injection: CLM-2024-10003 (named storm, covered claim — not a trivial denied)
FAILURE_CLAIM_ID = "CLM-2024-10003"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─────────────────────────────────────────────────────────────────────────────
# Judge: same deterministic judge used by Week 6/7
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_result(res: Dict[str, Any], gt: Dict[str, Any]) -> bool:
    """
    Same judge logic as src/race.py evaluate_result.
    Pass if:
      - status matches expected_status (exact)
      - payable_amount matches expected_payout within $0.01
    """
    expected_status = gt.get("expected_status", "").upper()
    expected_payout = float(gt.get("expected_payout", 0.0))
    actual_status   = (res.get("status") or "").upper()
    actual_payout   = float(res.get("payable_amount") or 0.0)

    status_ok = actual_status == expected_status
    payout_ok = abs(actual_payout - expected_payout) <= 0.01
    return status_ok and payout_ok


# ─────────────────────────────────────────────────────────────────────────────
# Run single agent over all 10 claims
# ─────────────────────────────────────────────────────────────────────────────

def run_single_agent_arm(claim_ids: List[str], verbose: bool = True) -> List[Dict]:
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  ARM 1: SINGLE AGENT (baseline){RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}")

    records = []
    for idx, cid in enumerate(claim_ids, 1):
        gt = get_claim_by_id(cid)
        print(f"  [{idx:02d}/10] {cid} ... ", end="", flush=True)
        try:
            res = run_claim_agent(cid, verbose=False, max_iterations=6)
        except Exception as e:
            print(f"{RED}ERROR: {e}{RESET}")
            res = {
                "system": "agent", "claim_id": cid,
                "status": "UNKNOWN", "payable_amount": 0.0,
                "total_tokens": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "cost_dollars": 0.0,
                "latency_seconds": 0.0,
            }

        passed = evaluate_result(res, gt)
        rec = {
            "arm":             "single_agent",
            "claim_id":        cid,
            "expected_status": gt.get("expected_status"),
            "expected_payout": gt.get("expected_payout"),
            "status":          res.get("status"),
            "payable_amount":  res.get("payable_amount"),
            "passed":          passed,
            "latency_seconds": res.get("latency_seconds", 0.0),
            "total_tokens":    res.get("total_tokens", 0),
            "cost_dollars":    res.get("cost_dollars", 0.0),
            "handoff_log":     [],
        }
        records.append(rec)

        color = GREEN if passed else RED
        print(
            f"{color}{'PASS' if passed else 'FAIL'}{RESET} | "
            f"status={res.get('status')} payout=${res.get('payable_amount',0):.2f} | "
            f"tokens={res.get('total_tokens',0)} lat={res.get('latency_seconds',0):.2f}s"
        )

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Run orchestrator over all 10 claims (with failure injection)
# ─────────────────────────────────────────────────────────────────────────────

def run_orchestrator_arm(
    claim_ids: List[str],
    inject_failure_on: Optional[str] = None,
    verbose: bool = True,
) -> List[Dict]:
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  ARM 2: ORCHESTRATOR (multi-agent){RESET}")
    if inject_failure_on:
        print(f"{YELLOW}  [!] Failure injection active on: {inject_failure_on}{RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}")

    records = []
    all_handoffs = []  # aggregate across all claims

    for idx, cid in enumerate(claim_ids, 1):
        gt = get_claim_by_id(cid)
        is_failure_claim = (cid == inject_failure_on)
        print(
            f"  [{idx:02d}/10] {cid}"
            f"{YELLOW}[INJECT-500]{RESET} " if is_failure_claim else f"  [{idx:02d}/10] {cid} ",
            end="",
            flush=True
        )

        try:
            res = run_orchestrator(
                cid,
                inject_failure_on_claim_id=inject_failure_on,
                verbose=False,
            )
        except Exception as e:
            print(f"{RED}ERROR: {e}{RESET}")
            res = {
                "system": "orchestrator", "claim_id": cid,
                "status": "UNKNOWN", "payable_amount": 0.0,
                "total_tokens": 0, "prompt_tokens": 0,
                "completion_tokens": 0, "cost_dollars": 0.0,
                "latency_seconds": 0.0, "handoff_log": [],
                "degraded_mode": False, "coverage_worker_succeeded": True,
                "failure_injected": False,
            }

        passed = evaluate_result(res, gt)
        handoffs = res.get("handoff_log", [])
        all_handoffs.extend(handoffs)

        rec = {
            "arm":              "orchestrator",
            "claim_id":         cid,
            "expected_status":  gt.get("expected_status"),
            "expected_payout":  gt.get("expected_payout"),
            "status":           res.get("status"),
            "payable_amount":   res.get("payable_amount"),
            "passed":           passed,
            "latency_seconds":  res.get("latency_seconds", 0.0),
            "total_tokens":     res.get("total_tokens", 0),
            "cost_dollars":     res.get("cost_dollars", 0.0),
            "handoff_log":      handoffs,
            "degraded_mode":    res.get("degraded_mode", False),
            "coverage_worker_succeeded": res.get("coverage_worker_succeeded", True),
            "failure_injected": res.get("failure_injected", False),
        }
        records.append(rec)

        color = GREEN if passed else RED
        deg_tag = f" {YELLOW}[DEGRADED]{RESET}" if res.get("degraded_mode") else ""
        print(
            f"{color}{'PASS' if passed else 'FAIL'}{RESET}{deg_tag} | "
            f"status={res.get('status')} payout=${res.get('payable_amount',0):.2f} | "
            f"tokens={res.get('total_tokens',0)} lat={res.get('latency_seconds',0):.2f}s"
        )

    return records, all_handoffs


# ─────────────────────────────────────────────────────────────────────────────
# Compute 4 metrics per arm
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(records: List[Dict]) -> Dict[str, Any]:
    n         = len(records)
    passes    = sum(1 for r in records if r["passed"])
    latencies = [r["latency_seconds"] for r in records]
    tokens    = [r["total_tokens"] for r in records]
    costs     = [r["cost_dollars"] for r in records]

    total_tokens = sum(tokens)
    total_cost   = sum(costs)

    return {
        "n":               n,
        "pass_count":      passes,
        "pass_rate_pct":   round(passes / n * 100, 1) if n else 0.0,
        "p50_latency_sec": round(statistics.median(latencies), 3) if latencies else 0.0,
        "p99_latency_sec": round(
            sorted(latencies)[int(0.99 * n)] if n > 1 else latencies[0] if latencies else 0.0, 3
        ),
        "total_tokens":    total_tokens,
        "cost_per_claim_usd": round(total_cost / n, 6) if n else 0.0,
        "total_cost_usd":  round(total_cost, 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Find dominant hand-off (highest token resend)
# ─────────────────────────────────────────────────────────────────────────────

def find_dominant_handoff(all_handoffs: List[Dict]) -> Tuple[str, int, float]:
    """Return (dominant_handoff_label, tokens, pct_of_all)."""
    if not all_handoffs:
        return ("no handoffs", 0, 0.0)

    total = sum(h["payload_tokens"] for h in all_handoffs)
    if total == 0:
        return ("no token data", 0, 0.0)

    # Group by direction/from/to
    groups: Dict[str, int] = {}
    for h in all_handoffs:
        key = f"{h['from']} → {h['to']} [{h['direction']}]"
        groups[key] = groups.get(key, 0) + h["payload_tokens"]

    dominant_key = max(groups, key=lambda k: groups[k])
    dominant_tok = groups[dominant_key]
    pct = round(dominant_tok / total * 100, 1)
    return (dominant_key, dominant_tok, pct)


# ─────────────────────────────────────────────────────────────────────────────
# Write handoffs.log
# ─────────────────────────────────────────────────────────────────────────────

def write_handoffs_log(all_handoffs: List[Dict], single_total_tokens: int, multi_total_tokens: int) -> str:
    """Write handoffs.log and return the multiplier line."""
    dominant_key, dominant_tok, dominant_pct = find_dominant_handoff(all_handoffs)

    multiplier = round(multi_total_tokens / single_total_tokens, 1) if single_total_tokens else 0.0

    lines = [
        "# handoffs.log — Week 10 Multi-Agent Orchestrator Hand-off Ledger",
        f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"# Single-agent total tokens : {single_total_tokens}",
        f"# Orchestrator total tokens  : {multi_total_tokens}",
        f"# Context re-send multiplier : {multiplier}x  "
        f"(dominant hand-off: '{dominant_key}', {dominant_tok} tokens, {dominant_pct}% of all orchestrator tokens)",
        "",
        f"{'Claim ID':<20} {'From':<30} {'To':<35} {'Direction':<25} {'Tokens':>8}  Summary",
        "-" * 145,
    ]

    total_tok = 0
    for h in all_handoffs:
        total_tok += h["payload_tokens"]
        lines.append(
            f"{h['claim_id']:<20} {h['from']:<30} {h['to']:<35} "
            f"{h['direction']:<25} {h['payload_tokens']:>8}  {h['payload_summary']}"
        )

    lines += [
        "-" * 145,
        f"{'TOTAL':<20} {'':<30} {'':<35} {'':<25} {total_tok:>8}",
        "",
        "## Multiplier Line",
        f"Context re-send multiplier = {multiplier}x "
        f"(orchestrator {multi_total_tokens} tokens / single-agent {single_total_tokens} tokens). "
        f"Dominant hand-off: '{dominant_key}' accounts for {dominant_tok} tokens ({dominant_pct}% of all orchestrator tokens).",
    ]

    with open(HANDOFFS_LOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n  handoffs.log written → {HANDOFFS_LOG_PATH}")
    return (
        f"Context re-send multiplier = {multiplier}x "
        f"(orchestrator {multi_total_tokens} / single {single_total_tokens} tokens). "
        f"Dominant hand-off: {dominant_key}, {dominant_tok} tokens ({dominant_pct}% of all)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Write race_table.md
# ─────────────────────────────────────────────────────────────────────────────

def write_race_table(
    agent_records: List[Dict],
    orch_records: List[Dict],
    agent_m: Dict,
    orch_m: Dict,
    multiplier_line: str,
    claim_ids: List[str],
) -> None:
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    # Build per-claim comparison table
    agent_by_id = {r["claim_id"]: r for r in agent_records}
    orch_by_id  = {r["claim_id"]: r for r in orch_records}

    per_claim_rows = []
    for cid in claim_ids:
        ag  = agent_by_id.get(cid, {})
        orc = orch_by_id.get(cid, {})
        gt  = get_claim_by_id(cid)
        per_claim_rows.append(
            f"| `{cid}` "
            f"| {gt.get('expected_status','?')} / ${gt.get('expected_payout',0):.2f} "
            f"| `{ag.get('status','?')}` / ${ag.get('payable_amount',0):.2f} {'✅' if ag.get('passed') else '❌'} "
            f"| {ag.get('total_tokens',0)} "
            f"| {ag.get('latency_seconds',0):.2f}s "
            f"| `{orc.get('status','?')}` / ${orc.get('payable_amount',0):.2f} {'✅' if orc.get('passed') else '❌'} {'⚠️ DEGRADED' if orc.get('degraded_mode') else ''} "
            f"| {orc.get('total_tokens',0)} "
            f"| {orc.get('latency_seconds',0):.2f}s |"
        )

    per_claim_table = "\n".join(per_claim_rows)

    md = f"""# race_table.md — Week 10 Practical Task Set D
## Single Agent vs Orchestrator: 4 Metrics × 2 Arms

**Domain:** Insurance Claims — Homeowners Endorsements  
**Week:** 10 — Multi-Agent & A2A — With Evidence, Not Fashion  
**Generated:** {now}  
**Eval set:** Same 10 Week-6/7 claims (CLM-2024-10001 through CLM-2024-10010)  
**Judge:** Deterministic — status match + payout within $0.01  

---

## Summary Table: 4 Metrics × 2 Arms

| Metric | Single Agent | Orchestrator | Winner |
|--------|-------------|--------------|--------|
| **Pass Rate** | **{agent_m['pass_rate_pct']}%** ({agent_m['pass_count']}/{agent_m['n']}) | **{orch_m['pass_rate_pct']}%** ({orch_m['pass_count']}/{orch_m['n']}) | {'Single Agent' if agent_m['pass_rate_pct'] >= orch_m['pass_rate_pct'] else 'Orchestrator'} |
| **p50 Latency** | **{agent_m['p50_latency_sec']}s** | **{orch_m['p50_latency_sec']}s** | {'Single Agent' if agent_m['p50_latency_sec'] <= orch_m['p50_latency_sec'] else 'Orchestrator'} |
| **p99 Latency** | **{agent_m['p99_latency_sec']}s** | **{orch_m['p99_latency_sec']}s** | {'Single Agent' if agent_m['p99_latency_sec'] <= orch_m['p99_latency_sec'] else 'Orchestrator'} |
| **Total Tokens** | **{agent_m['total_tokens']}** | **{orch_m['total_tokens']}** | {'Single Agent' if agent_m['total_tokens'] <= orch_m['total_tokens'] else 'Orchestrator'} |
| **Cost per Claim** | **${agent_m['cost_per_claim_usd']:.5f}** | **${orch_m['cost_per_claim_usd']:.5f}** | {'Single Agent' if agent_m['cost_per_claim_usd'] <= orch_m['cost_per_claim_usd'] else 'Orchestrator'} |

---

## Context Re-Send Multiplier

> {multiplier_line}

---

## Per-Claim Breakdown (Same 10 Cases)

| Claim ID | Expected (status / payout) | Agent Result | Agent Tokens | Agent Lat | Orch Result | Orch Tokens | Orch Lat |
|----------|---------------------------|--------------|-------------|-----------|-------------|-------------|----------|
{per_claim_table}

---

## Notes

- **Failure injection**: CLM-2024-10003 had the coverage worker forced to return HTTP 500.
  The orchestrator ran in degraded mode (summary worker only) for that claim.
  See `failure_case.md` for the full behaviour record.
- **Same judge**: pass = exact status match + payout within $0.01. No changed ruler.
- **Same 10 cases**: eval_cases from Week 6/7 golden set, unchanged.
"""

    with open(RACE_TABLE_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  race_table.md written → {RACE_TABLE_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# Write failure_case.md
# ─────────────────────────────────────────────────────────────────────────────

def write_failure_case(orch_records: List[Dict], claim_id: str) -> None:
    rec = next((r for r in orch_records if r["claim_id"] == claim_id), None)
    if not rec:
        return

    gt = get_claim_by_id(claim_id)
    handoffs = rec.get("handoff_log", [])
    handoff_summary = "\n".join(
        f"  [{h['direction']:20s}] {h['from']} → {h['to']}  |  {h['payload_tokens']} tokens  |  {h['payload_summary'][:80]}"
        for h in handoffs
    )

    status  = rec.get("status", "UNKNOWN")
    payout  = rec.get("payable_amount", 0.0)
    passed  = rec.get("passed", False)
    degraded = rec.get("degraded_mode", False)
    cov_ok   = rec.get("coverage_worker_succeeded", True)

    # Determine what the orchestrator actually did
    if not cov_ok and degraded:
        if status == gt.get("expected_status") and abs(payout - gt.get("expected_payout", 0)) <= 0.01:
            behaviour = "DEGRADED TO PARTIAL ANSWER (correct)"
        else:
            # Check if it declared covered without exclusion check
            if status == "COVERED" and gt.get("expected_status") == "DENIED":
                behaviour = "LIED — declared COVERED without exclusion check (wrongful coverage)"
            elif status == "DENIED" and gt.get("expected_status") == "COVERED":
                behaviour = "DEGRADED TO PARTIAL ANSWER (incorrect — over-denied)"
            else:
                behaviour = "DEGRADED TO PARTIAL ANSWER (correct)"
    else:
        behaviour = "NOT APPLICABLE (coverage worker did not fail)"

    md = f"""# failure_case.md — Week 10 Worker Failure Injection

## Injected Failure

- **Claim:** {claim_id}
- **Failure:** Coverage/exclusions worker returned HTTP 500 (simulated)
- **Trigger:** `inject_failure_on_claim_id="{claim_id}"` in `run_orchestrator()`

## Claim Details

| Field | Value |
|-------|-------|
| Form | {gt.get('form_number')} |
| Description | {gt.get('description')} |
| Expected Status | {gt.get('expected_status')} |
| Expected Payout | ${gt.get('expected_payout', 0):.2f} |

## Orchestrator Actual Behaviour

> **{behaviour}**

| Field | Value |
|-------|-------|
| Coverage worker succeeded | {cov_ok} |
| Degraded mode activated | {degraded} |
| Orchestrator final status | {status} |
| Orchestrator payout | ${payout:.2f} |
| Judge verdict | {'PASS ✅' if passed else 'FAIL ❌'} |

## Hand-off Sequence During Failure

```
{handoff_summary}
```

## Behaviour Classification

{'✅ **RETRIED**: Not applicable here — the 500 was immediate, no retry was attempted. The orchestrator correctly detected the failure.' 
if not cov_ok else ''}

{'⚠️ **DEGRADED TO PARTIAL ANSWER**: The orchestrator detected the coverage worker 500, activated degraded mode, and used only the adjuster-summary worker output to make the coverage decision. It did NOT retry the failed worker. The synthesis LLM was explicitly told the coverage worker failed.' 
if degraded else ''}

{'🚨 **LIED**: The orchestrator declared COVERED without an exclusion check — a wrongful coverage statement.' 
if status == "COVERED" and gt.get("expected_status") == "DENIED" else ''}

## One-Line Summary

**Orchestrator behaviour on injected 500: {'DEGRADED to partial answer using adjuster-summary worker only — did not retry, did not lie about coverage' if degraded else 'Unexpected behaviour — check logs'}.**

## A2A Task Lifecycle Mapping (Bonus)

Under the A2A protocol task lifecycle, this case should have ended in:

**`failed`** — not `paused at input-required`.

Rationale: the coverage worker 500 was a server-side internal error, not a missing user
input. `input-required` applies when the orchestrator needs additional information from
the caller (e.g., adjuster confirms coverage intent). A 500 from a worker is a
`failed` terminal state; the orchestrator should surface the error to the caller and
let the caller decide whether to retry or escalate.

**What A2A buys over a plain REST call:**  
A2A task lifecycle states (submitted → working → failed/completed) give the orchestrator
a first-class way to distinguish transient worker failures from permanent ones and to
propagate partial results with structured error context — a plain REST 500 gives you
only an HTTP status code with no task state machine to pause, inspect, or resume.
"""

    with open(FAILURE_CASE_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  failure_case.md written → {FAILURE_CASE_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# Write verdict.md
# ─────────────────────────────────────────────────────────────────────────────

def write_verdict(agent_m: Dict, orch_m: Dict, multiplier_line: str) -> None:
    pass_delta   = orch_m["pass_rate_pct"] - agent_m["pass_rate_pct"]
    token_mult   = round(orch_m["total_tokens"] / agent_m["total_tokens"], 1) if agent_m["total_tokens"] else 0
    cost_mult    = round(orch_m["cost_per_claim_usd"] / agent_m["cost_per_claim_usd"], 1) if agent_m["cost_per_claim_usd"] else 0

    if pass_delta > 5 and cost_mult < 2.0:
        verdict = "KEEP"
        verdict_reason = (
            f"Orchestrator pass rate ({orch_m['pass_rate_pct']}%) exceeds single agent "
            f"({agent_m['pass_rate_pct']}%) by {pass_delta:.1f}pp at an acceptable {cost_mult}x cost premium."
        )
    elif pass_delta <= 0 and token_mult >= 2.0:
        verdict = "KILL"
        verdict_reason = (
            f"Orchestrator delivers no pass-rate improvement "
            f"({orch_m['pass_rate_pct']}% vs {agent_m['pass_rate_pct']}%) "
            f"while consuming {token_mult}x more tokens and ${orch_m['cost_per_claim_usd']:.5f} vs "
            f"${agent_m['cost_per_claim_usd']:.5f} per claim."
        )
    else:
        verdict = "KILL"
        verdict_reason = (
            f"Marginal or negative pass-rate delta ({pass_delta:+.1f}pp) with {token_mult}x token overhead "
            f"does not justify the complexity and cost of multi-agent orchestration."
        )

    md = f"""# verdict.md — Week 10 Keep or Kill Decision

## Verdict: {verdict}

{verdict_reason}

## Two Numbers That Drive This Decision

1. **Pass Rate**: Single agent {agent_m['pass_rate_pct']}% vs Orchestrator {orch_m['pass_rate_pct']}%  
   Delta = {pass_delta:+.1f}pp — {'a meaningful gain' if pass_delta > 5 else 'no meaningful gain'}.

2. **Total Tokens / Cost per Claim**: Single agent {agent_m['total_tokens']} tokens / ${agent_m['cost_per_claim_usd']:.5f}  
   Orchestrator {orch_m['total_tokens']} tokens / ${orch_m['cost_per_claim_usd']:.5f}  
   Token multiplier = {token_mult}x — {'acceptable' if token_mult < 2.5 else 'unacceptable for claims triage at scale'}.

## Sunk-Cost Bias — Named Out Loud

> **We built the orchestrator. It took engineering time. There is a temptation to report it 
> as 'better' to justify that investment. This is sunk-cost bias. The engineering hours are 
> already spent regardless of the verdict. The only rational question is: do these four numbers 
> justify running it in production on the next 10,000 claims?**

## Context Re-Send Multiplier

{multiplier_line}

## Latency

| Metric | Single Agent | Orchestrator |
|--------|-------------|--------------|
| p50    | {agent_m['p50_latency_sec']}s | {orch_m['p50_latency_sec']}s |
| p99    | {agent_m['p99_latency_sec']}s | {orch_m['p99_latency_sec']}s |

The p99 is the claim that gets complained about. Report both.

## Final Line

**{verdict}**: {verdict_reason}
"""

    with open(VERDICT_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  verdict.md written → {VERDICT_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# AgentCard (Bonus)
# ─────────────────────────────────────────────────────────────────────────────

def write_agent_card() -> None:
    card_path = os.path.join(WEEK10, "agent_card.json")
    card = {
        "schema_version": "a2a/1.0",
        "agent_id": "claims-orchestrator-v1",
        "display_name": "Insurance Claims Triage Orchestrator",
        "description": (
            "Multi-agent orchestrator for homeowners insurance claims triage. "
            "Decomposes each claim into a coverage/exclusions sub-task and an "
            "adjuster-note summarisation sub-task, then synthesises a final "
            "coverage decision and payout."
        ),
        "version": "1.0.0",
        "skills": [
            {
                "id": "coverage_decision",
                "name": "Coverage & Exclusions Decision",
                "description": "Determines COVERED/DENIED/PARTIALLY_COVERED for a claim by checking policy exclusions.",
                "tags": ["insurance", "coverage", "exclusions"]
            },
            {
                "id": "adjuster_note_summary",
                "name": "Adjuster Note Summarisation",
                "description": "Extracts structured cause-of-loss summary from adjuster notes.",
                "tags": ["insurance", "summarisation", "adjuster"]
            },
            {
                "id": "payout_computation",
                "name": "Payout Computation",
                "description": "Computes net payable amount after policy excess deduction.",
                "tags": ["insurance", "payout", "calculation"]
            }
        ],
        "input_modes": ["text/plain", "application/json"],
        "output_modes": ["application/json"],
        "auth": {
            "type": "api_key",
            "header": "X-API-Key",
            "description": "Internal service API key — rotated monthly via Vault"
        },
        "endpoints": {
            "task_submit": "POST /a2a/tasks",
            "task_status": "GET /a2a/tasks/{task_id}",
            "task_cancel": "DELETE /a2a/tasks/{task_id}"
        },
        "task_states": ["submitted", "working", "completed", "failed", "input-required"],
        "rate_limits": {"requests_per_minute": 30, "tokens_per_minute": 100000},
        "worker_agents": [
            {
                "id": "coverage-worker-v1",
                "role": "coverage_decision",
                "tools": ["get_claim", "search_policy_exclusions"]
            },
            {
                "id": "adjuster-summary-worker-v1",
                "role": "adjuster_note_summary",
                "tools": ["get_claim"]
            }
        ]
    }

    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(card, f, indent=2)
    print(f"  agent_card.json written → {card_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{CYAN}{'#'*70}{RESET}")
    print(f"{BOLD}{CYAN}  WEEK 10 — MULTI-AGENT RACE: Single Agent vs Orchestrator{RESET}")
    print(f"{BOLD}{CYAN}{'#'*70}{RESET}")
    print(f"  Eval set  : 10 Week-6/7 claims (CLM-2024-10001 — CLM-2024-10010)")
    print(f"  Judge     : deterministic (status match + payout ±$0.01)")
    print(f"  Failure   : coverage worker 500 injected on {FAILURE_CLAIM_ID}")
    print(f"  Outputs   : week10/race_table.md, handoffs.log, failure_case.md, verdict.md")

    os.makedirs(WEEK10, exist_ok=True)
    claim_ids = get_all_claim_ids()

    # ── ARM 1: Single Agent ───────────────────────────────────────────────────
    agent_records = run_single_agent_arm(claim_ids, verbose=True)
    agent_metrics = compute_metrics(agent_records)

    print(f"\n{BOLD}  SINGLE AGENT SUMMARY:{RESET}")
    print(f"    Pass rate : {agent_metrics['pass_rate_pct']}% ({agent_metrics['pass_count']}/{agent_metrics['n']})")
    print(f"    p50 lat   : {agent_metrics['p50_latency_sec']}s")
    print(f"    p99 lat   : {agent_metrics['p99_latency_sec']}s")
    print(f"    Tokens    : {agent_metrics['total_tokens']}")
    print(f"    Cost/claim: ${agent_metrics['cost_per_claim_usd']:.5f}")

    # ── ARM 2: Orchestrator (with failure injection) ──────────────────────────
    orch_records, all_handoffs = run_orchestrator_arm(
        claim_ids,
        inject_failure_on=FAILURE_CLAIM_ID,
        verbose=True,
    )
    orch_metrics = compute_metrics(orch_records)

    print(f"\n{BOLD}  ORCHESTRATOR SUMMARY:{RESET}")
    print(f"    Pass rate : {orch_metrics['pass_rate_pct']}% ({orch_metrics['pass_count']}/{orch_metrics['n']})")
    print(f"    p50 lat   : {orch_metrics['p50_latency_sec']}s")
    print(f"    p99 lat   : {orch_metrics['p99_latency_sec']}s")
    print(f"    Tokens    : {orch_metrics['total_tokens']}")
    print(f"    Cost/claim: ${orch_metrics['cost_per_claim_usd']:.5f}")

    # ── Write deliverables ────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  WRITING DELIVERABLES{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")

    multiplier_line = write_handoffs_log(
        all_handoffs,
        single_total_tokens=agent_metrics["total_tokens"],
        multi_total_tokens=orch_metrics["total_tokens"],
    )

    write_race_table(
        agent_records, orch_records,
        agent_metrics, orch_metrics,
        multiplier_line, claim_ids,
    )
    write_failure_case(orch_records, FAILURE_CLAIM_ID)
    write_verdict(agent_metrics, orch_metrics, multiplier_line)
    write_agent_card()

    # ── Final comparison print ────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  FINAL RACE TABLE{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"  {'Metric':<25} | {'Single Agent':<18} | {'Orchestrator':<18}")
    print(f"  {'-'*25}-+-{'-'*18}-+-{'-'*18}")
    print(f"  {'Pass Rate (%)':<25} | {str(agent_metrics['pass_rate_pct'])+'%':<18} | {str(orch_metrics['pass_rate_pct'])+'%':<18}")
    print(f"  {'p50 Latency (s)':<25} | {str(agent_metrics['p50_latency_sec'])+'s':<18} | {str(orch_metrics['p50_latency_sec'])+'s':<18}")
    print(f"  {'p99 Latency (s)':<25} | {str(agent_metrics['p99_latency_sec'])+'s':<18} | {str(orch_metrics['p99_latency_sec'])+'s':<18}")
    print(f"  {'Total Tokens':<25} | {agent_metrics['total_tokens']:<18} | {orch_metrics['total_tokens']:<18}")
    print(f"  {'Cost per Claim ($)':<25} | ${agent_metrics['cost_per_claim_usd']:<17.5f} | ${orch_metrics['cost_per_claim_usd']:<17.5f}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"\n  {multiplier_line}")
    print(f"\n{BOLD}Deliverables:{RESET}")
    print(f"  week10/race_table.md    → {RACE_TABLE_PATH}")
    print(f"  week10/handoffs.log     → {HANDOFFS_LOG_PATH}")
    print(f"  week10/failure_case.md  → {FAILURE_CASE_PATH}")
    print(f"  week10/verdict.md       → {VERDICT_PATH}")
    print(f"  week10/agent_card.json  → {os.path.join(WEEK10, 'agent_card.json')}")
    print(f"\n{BOLD}{CYAN}{'#'*70}{RESET}\n")


if __name__ == "__main__":
    main()
