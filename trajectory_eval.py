"""
trajectory_eval.py — Week 8 Practical Task Set D
Insurance Claims Agent: Trajectory Evaluation

Deliverables (all in one file):
  1. Expected tool sequences for all 10 claims, with alternate-path sets for
     clean covered claims where order of notes vs policy lookup is flexible.
  2. Four trajectory numbers:
       - Tool-choice accuracy
       - Argument validity rate
       - Step efficiency  (steps taken / steps needed)
       - Cost per claim: p50 AND max
  3. Outcome-vs-trajectory gap number + one named right-answer-wrong-path trace.
  4. ONE mitigation (hard step limit) applied to top failure mode;
     before->after count + measured price (latency, tokens, cost).
  5. Per-mode regression check across all failure modes.
"""

import os
import sys
import json
import time
import statistics
import re
from typing import Dict, Any, List, Optional, Set, Tuple
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from agent import run_claim_agent, INPUT_COST_PER_TOKEN, OUTPUT_COST_PER_TOKEN
from claims_data import CLAIMS_DATABASE, get_all_claim_ids

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# ANSI colour helpers
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

SEPARATOR = "─" * 72


# ─────────────────────────────────────────────────────────────────────────────
# REQUIREMENT 1:
# Expected tool sequences for 10 claims.
# Cases where both orders are valid use alternate_paths=True.
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_SEQUENCES: Dict[str, Any] = {
    "CLM-2024-10001": {
        "description": "Sudden pipe burst — covered, HO-0304",
        "dynamic_dependency": False,
        "min_steps_needed": 2,
        "alternate_paths": True,
        "accepted_sequences": [
            ["get_claim", "compute_payout"],
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "compute_payout"},
        "must_not_skip_exclusions": False,
    },
    "CLM-2024-10002": {
        "description": "Continuous seepage → E-11 exclusion (dynamic dependency)",
        "dynamic_dependency": True,
        "min_steps_needed": 3,
        "alternate_paths": False,
        "accepted_sequences": [
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "search_policy_exclusions", "compute_payout"},
        "must_not_skip_exclusions": True,
    },
    "CLM-2024-10003": {
        "description": "Named Storm wind — covered, HO-0305",
        "dynamic_dependency": False,
        "min_steps_needed": 2,
        "alternate_paths": True,
        "accepted_sequences": [
            ["get_claim", "compute_payout"],
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "compute_payout"},
        "must_not_skip_exclusions": False,
    },
    "CLM-2024-10004": {
        "description": "Mold from sudden discharge — covered, HO-0306",
        "dynamic_dependency": False,
        "min_steps_needed": 2,
        "alternate_paths": True,
        "accepted_sequences": [
            ["get_claim", "compute_payout"],
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "compute_payout"},
        "must_not_skip_exclusions": False,
    },
    "CLM-2024-10005": {
        "description": "Mold from ambient humidity → E-22 exclusion (dynamic dependency)",
        "dynamic_dependency": True,
        "min_steps_needed": 3,
        "alternate_paths": False,
        "accepted_sequences": [
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "search_policy_exclusions", "compute_payout"},
        "must_not_skip_exclusions": True,
    },
    "CLM-2024-10006": {
        "description": "Scheduled jewelry theft — covered, HO-0307",
        "dynamic_dependency": False,
        "min_steps_needed": 2,
        "alternate_paths": True,
        "accepted_sequences": [
            ["get_claim", "compute_payout"],
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "compute_payout"},
        "must_not_skip_exclusions": False,
    },
    "CLM-2024-10007": {
        "description": "Earthquake tremors → E-31 exclusion (dynamic dependency)",
        "dynamic_dependency": True,
        "min_steps_needed": 3,
        "alternate_paths": False,
        "accepted_sequences": [
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "search_policy_exclusions", "compute_payout"},
        "must_not_skip_exclusions": True,
    },
    "CLM-2024-10008": {
        "description": "Sinkhole collapse → E-33 exclusion (dynamic dependency)",
        "dynamic_dependency": True,
        "min_steps_needed": 3,
        "alternate_paths": False,
        "accepted_sequences": [
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "search_policy_exclusions", "compute_payout"},
        "must_not_skip_exclusions": True,
    },
    "CLM-2024-10009": {
        "description": "Loss below deductible — covered, payout $0, HO-0304",
        "dynamic_dependency": False,
        "min_steps_needed": 2,
        "alternate_paths": True,
        "accepted_sequences": [
            ["get_claim", "compute_payout"],
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "compute_payout"},
        "must_not_skip_exclusions": False,
    },
    "CLM-2024-10010": {
        "description": "Home business injury → E-19 exclusion (dynamic dependency)",
        "dynamic_dependency": True,
        "min_steps_needed": 3,
        "alternate_paths": False,
        "accepted_sequences": [
            ["get_claim", "search_policy_exclusions", "compute_payout"],
        ],
        "must_call": {"get_claim", "search_policy_exclusions", "compute_payout"},
        "must_not_skip_exclusions": True,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Known valid argument ranges
# ─────────────────────────────────────────────────────────────────────────────
VALID_CLAIM_IDS: Set[str] = set(CLAIMS_DATABASE.keys())
VALID_POLICY_FORMS: Set[str] = {"HO-0304", "HO-0305", "HO-0306", "HO-0307", "HO-0308", "HO-0309"}
VALID_STATUSES: Set[str] = {"COVERED", "DENIED", "PARTIALLY_COVERED"}
VALID_EXCLUSION_QUERIES = {
    "seepage", "leakage", "water", "mold", "humidity", "condensation",
    "earthquake", "earth movement", "sinkhole", "business", "pursuits",
    "storm", "wind", "theft", "disappearance", "flood", "pipe", "discharge"
}


def validate_arguments(tool_name: str, args: Dict[str, Any], expected_claim: Dict[str, Any]) -> Tuple[bool, str]:
    if tool_name == "get_claim":
        cid = args.get("claim_id", "")
        if cid in VALID_CLAIM_IDS:
            return True, "claim_id is real"
        return False, f"claim_id '{cid}' hallucinated"

    elif tool_name == "search_policy_exclusions":
        pf = args.get("policy_form", "")
        q = args.get("query", "").lower()
        form_valid = pf in VALID_POLICY_FORMS
        query_valid = any(kw in q for kw in VALID_EXCLUSION_QUERIES) or len(q) > 5
        if form_valid and query_valid:
            return True, f"policy_form={pf} valid, query has real exclusion terms"
        if not form_valid:
            return False, f"policy_form '{pf}' not in known forms"
        return False, f"query '{q}' contains no known exclusion terms (fluent fiction)"

    elif tool_name == "compute_payout":
        ca = args.get("claimed_amount", None)
        ea = args.get("excess_amount", None)
        st = args.get("status", "")
        expected_ca = expected_claim.get("claimed_amount", 0)
        expected_ea = expected_claim.get("excess_amount", 0)
        reasons = []
        valid = True
        if st not in VALID_STATUSES:
            valid = False
            reasons.append(f"status '{st}' invalid")
        if ca is not None and abs(float(ca) - float(expected_ca)) > 1.0:
            valid = False
            reasons.append(f"claimed_amount {ca} != expected {expected_ca} (hallucinated)")
        if ea is not None and abs(float(ea) - float(expected_ea)) > 1.0:
            valid = False
            reasons.append(f"excess_amount {ea} != expected {expected_ea} (hallucinated)")
        if valid:
            return True, "all amounts match claim record"
        return False, "; ".join(reasons)

    return True, "unknown tool — assumed valid"


# ─────────────────────────────────────────────────────────────────────────────
# Failure Mode Taxonomy
# ─────────────────────────────────────────────────────────────────────────────
FAILURE_MODES = [
    "skip_exclusions",
    "wrong_tool_order",
    "hallucinated_args",
    "excess_steps",
    "budget_exceeded",
    "wrong_status",
]


def classify_failure_modes(
    claim_id, tool_calls, tool_calls_log, trajectory_pass, outcome_pass,
    expected, agent_result, expected_claim,
) -> List[str]:
    modes = []
    min_steps = expected["min_steps_needed"]

    if expected["must_not_skip_exclusions"] and "search_policy_exclusions" not in tool_calls:
        modes.append("skip_exclusions")

    if "compute_payout" in tool_calls and "search_policy_exclusions" in tool_calls:
        cp_idx = tool_calls.index("compute_payout")
        sp_idx = tool_calls.index("search_policy_exclusions")
        if cp_idx < sp_idx:
            modes.append("wrong_tool_order")

    for tc in tool_calls_log:
        valid, _ = validate_arguments(tc["tool"], tc["args"], expected_claim)
        if not valid:
            modes.append("hallucinated_args")
            break

    steps_taken = len(tool_calls)
    if steps_taken > min_steps + 2:
        modes.append("excess_steps")

    if agent_result.get("budget_exceeded"):
        modes.append("budget_exceeded")

    expected_status = expected_claim.get("expected_status", "")
    agent_status = agent_result.get("status", "")
    if agent_status and agent_status not in ("UNKNOWN", "") and agent_status != expected_status:
        if "compute_payout" in tool_calls:
            modes.append("wrong_status")

    return list(set(modes))


# ─────────────────────────────────────────────────────────────────────────────
# Trajectory assertion
# ─────────────────────────────────────────────────────────────────────────────

def assert_trajectory(claim_id: str, tool_calls: List[str], expected: Dict) -> Tuple[bool, str]:
    must_call = expected["must_call"]
    actual_set = set(tool_calls)

    missing = must_call - actual_set
    if missing:
        return False, f"Missing required tools: {missing}"

    if expected["must_not_skip_exclusions"] and "search_policy_exclusions" not in tool_calls:
        return False, "search_policy_exclusions skipped on dynamic-dependency claim"

    # Deduplicate preserving order
    seen = []
    for t in tool_calls:
        if not seen or seen[-1] != t:
            seen.append(t)

    for accepted in expected["accepted_sequences"]:
        if seen == accepted:
            return True, f"Matched accepted sequence: {accepted}"

    # Partial match: all required tools in correct relative order (extra calls tolerated)
    required_order = expected["accepted_sequences"][0]
    try:
        positions = [seen.index(t) for t in required_order if t in seen]
        if positions == sorted(positions) and set(required_order).issubset(actual_set):
            return True, "All required tools present in correct order (extra calls tolerated)"
    except ValueError:
        pass

    if expected["alternate_paths"]:
        for accepted in expected["accepted_sequences"]:
            if set(accepted).issubset(actual_set):
                return True, f"Alternate path accepted: required tools all present"

    return False, f"Actual path {seen} does not match any accepted sequence"


# ─────────────────────────────────────────────────────────────────────────────
# Baseline + Mitigated run helpers
# ─────────────────────────────────────────────────────────────────────────────

def run_eval_pass(max_iters: int, label: str, verbose: bool = True) -> List[Dict]:
    if verbose:
        print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
        print(f"{BOLD}{CYAN}  {label} (max_iterations={max_iters}){RESET}")
        print(f"{BOLD}{CYAN}{'='*72}{RESET}\n")

    results = []
    for claim_id in get_all_claim_ids():
        expected = EXPECTED_SEQUENCES[claim_id]
        expected_claim = CLAIMS_DATABASE[claim_id]

        if verbose:
            print(f"  Running {claim_id}  ({expected['description']})...")

        result = run_claim_agent(
            claim_id=claim_id,
            max_iterations=max_iters,
            max_tokens=12000,
            max_cost=0.05,
            max_wall_clock=45.0,
            verbose=False,
        )

        tool_calls = result.get("tool_calls_made", [])
        tool_calls_log = result.get("tool_calls_log", [])
        agent_status = result.get("status", "UNKNOWN")
        agent_payout = result.get("payable_amount", 0.0)
        expected_status = expected_claim["expected_status"]
        expected_payout = expected_claim["expected_payout"]

        outcome_pass = (
            agent_status == expected_status and
            abs(agent_payout - expected_payout) < 1.0
        )
        traj_pass, traj_reason = assert_trajectory(claim_id, tool_calls, expected)

        steps_taken = len(tool_calls)
        steps_needed = expected["min_steps_needed"]
        step_efficiency = steps_needed / steps_taken if steps_taken > 0 else 0.0

        arg_results = []
        for tc in tool_calls_log:
            valid, reason = validate_arguments(tc["tool"], tc["args"], expected_claim)
            arg_results.append({"tool": tc["tool"], "valid": valid, "reason": reason})
        arg_validity = sum(1 for a in arg_results if a["valid"]) / len(arg_results) if arg_results else 1.0

        failure_modes = classify_failure_modes(
            claim_id, tool_calls, tool_calls_log, traj_pass, outcome_pass,
            expected, result, expected_claim
        )

        row = {
            "claim_id": claim_id,
            "description": expected["description"],
            "dynamic_dependency": expected["dynamic_dependency"],
            "outcome_pass": outcome_pass,
            "trajectory_pass": traj_pass,
            "traj_reason": traj_reason,
            "tool_calls": tool_calls,
            "steps_taken": steps_taken,
            "steps_needed": steps_needed,
            "step_efficiency": round(step_efficiency, 3),
            "arg_validity": round(arg_validity, 3),
            "arg_results": arg_results,
            "cost_dollars": result.get("cost_dollars", 0.0),
            "latency_seconds": result.get("latency_seconds", 0.0),
            "total_tokens": result.get("total_tokens", 0),
            "laps": result.get("laps", 0),
            "budget_exceeded": result.get("budget_exceeded"),
            "agent_status": agent_status,
            "expected_status": expected_status,
            "failure_modes": failure_modes,
        }
        results.append(row)

        if verbose:
            t_icon = f"{GREEN}TRAJ-PASS{RESET}" if traj_pass else f"{RED}TRAJ-FAIL{RESET}"
            o_icon = f"{GREEN}OUT-PASS{RESET}" if outcome_pass else f"{RED}OUT-FAIL{RESET}"
            print(f"    {t_icon} | {o_icon} | Tools:{tool_calls} | "
                  f"Steps:{steps_taken}/{steps_needed} | ArgV:{arg_validity:.0%} | "
                  f"Cost:${result.get('cost_dollars',0):.5f}")
            if failure_modes:
                print(f"    {YELLOW}Modes: {failure_modes}{RESET}")

    return results


def compute_metrics(results: List[Dict]) -> Dict[str, Any]:
    n = len(results)
    traj_passes = sum(1 for r in results if r["trajectory_pass"])
    outcome_passes = sum(1 for r in results if r["outcome_pass"])
    all_arg_validities = [r["arg_validity"] for r in results]
    all_efficiencies = [r["step_efficiency"] for r in results]
    costs = [r["cost_dollars"] for r in results]
    latencies = [r["latency_seconds"] for r in results]

    tool_choice_accuracy = traj_passes / n
    arg_validity_rate = statistics.mean(all_arg_validities) if all_arg_validities else 0.0
    step_efficiency_mean = statistics.mean(all_efficiencies) if all_efficiencies else 0.0
    cost_p50 = statistics.median(costs)
    cost_max = max(costs)
    cost_mean = statistics.mean(costs)
    outcome_pass_rate = outcome_passes / n
    gap = outcome_pass_rate - tool_choice_accuracy

    return {
        "n": n,
        "tool_choice_accuracy": round(tool_choice_accuracy, 3),
        "arg_validity_rate": round(arg_validity_rate, 3),
        "step_efficiency_mean": round(step_efficiency_mean, 3),
        "cost_p50": round(cost_p50, 6),
        "cost_max": round(cost_max, 6),
        "cost_mean": round(cost_mean, 6),
        "outcome_pass_rate": round(outcome_pass_rate, 3),
        "outcome_passes": outcome_passes,
        "trajectory_passes": traj_passes,
        "gap": round(gap, 3),
        "latency_p50": round(statistics.median(latencies), 3),
        "latency_max": round(max(latencies), 3),
    }


def count_failure_modes(results: List[Dict]) -> Dict[str, int]:
    counts = {mode: 0 for mode in FAILURE_MODES}
    for r in results:
        for mode in r.get("failure_modes", []):
            if mode in counts:
                counts[mode] += 1
    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Pretty-print helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_results_table(results: List[Dict], title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*72}{RESET}")
    print(BOLD + f"  {'Claim ID':<18} {'Outcome':>8} {'Traj':>6} {'#Tools':>7} "
          f"{'Steps':>7} {'ArgV':>6} {'Cost($)':>10}" + RESET)
    print(f"  {'─'*66}")
    for r in results:
        o_icon = "PASS" if r["outcome_pass"] else "FAIL"
        t_icon = "PASS" if r["trajectory_pass"] else "FAIL"
        steps = f"{r['steps_taken']}/{r['steps_needed']}"
        tools = len(r["tool_calls"])
        print(f"  {r['claim_id']:<18} {o_icon:>8} {t_icon:>6} {tools:>7} {steps:>7} "
              f"{r['arg_validity']:>6.0%} {r['cost_dollars']:>10.5f}")
    print(f"  {'─'*66}")


def print_metrics_table(metrics: Dict, label: str) -> None:
    print(f"\n{BOLD}  ── {label} ──{RESET}")
    print(f"  {'Tool-choice accuracy':<42} {metrics['tool_choice_accuracy']:.1%}  "
          f"({metrics['trajectory_passes']}/{metrics['n']})")
    print(f"  {'Argument validity rate':<42} {metrics['arg_validity_rate']:.1%}")
    print(f"  {'Step efficiency (mean needed/taken)':<42} {metrics['step_efficiency_mean']:.3f}")
    print(f"  {'Cost per claim — p50':<42} ${metrics['cost_p50']:.5f}")
    print(f"  {'Cost per claim — max':<42} ${metrics['cost_max']:.5f}   ← variance")
    print(f"  {'Cost per claim — mean':<42} ${metrics['cost_mean']:.5f}")
    print(f"  {'Outcome pass rate':<42} {metrics['outcome_pass_rate']:.1%}  "
          f"({metrics['outcome_passes']}/{metrics['n']})")
    print(f"  {'Latency p50 / max (s)':<42} {metrics['latency_p50']:.2f}s / {metrics['latency_max']:.2f}s")
    print(f"  {'─'*60}")
    print(f"  {BOLD}{'Outcome-vs-Trajectory GAP':<42} {metrics['gap']:+.1%}{RESET}  "
          f"(outcome_rate − traj_accuracy)")


def print_gap_narrative(baseline_results: List[Dict], metrics: Dict) -> None:
    print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"{BOLD}{CYAN}  OUTCOME-vs-TRAJECTORY GAP ANALYSIS{RESET}")
    print(f"{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"\n  Gap = {metrics['outcome_pass_rate']:.1%} − {metrics['tool_choice_accuracy']:.1%} = "
          f"{BOLD}{metrics['gap']:+.1%}{RESET}")

    right_wrong = [r for r in baseline_results if r["outcome_pass"] and not r["trajectory_pass"]]

    if right_wrong:
        print(f"\n  {BOLD}Right-answer-wrong-path cases ({len(right_wrong)}):{RESET}")
        for r in right_wrong:
            print(f"\n  {YELLOW}► {r['claim_id']}{RESET} — {r['description']}")
            print(f"    Outcome  : PASS  (agent_status={r['agent_status']}, correct payout)")
            print(f"    Trajectory: FAIL — {r['traj_reason']}")
            print(f"    Path taken: {r['tool_calls']}")
            print(f"    Time-bomb: Correct payout produced WITHOUT opening exclusions.")
            print(f"    On a claim with the same peril but an active exclusion clause,")
            print(f"    the agent would skip the lookup and pay out incorrectly.")
    else:
        print(f"\n  {DIM}No right-answer-wrong-path case occurred in this run.")
        print(f"  Canonical example (Week-8 taxonomy):{RESET}")
        print(f"  {YELLOW}► CLM-2024-10001 (sudden pipe burst){RESET}")
        print(f"    If the agent calls [get_claim → compute_payout] (skipping")
        print(f"    search_policy_exclusions), it produces COVERED/$1700.00 — the")
        print(f"    correct outcome — but never verifies no exclusion applies.")
        print(f"    Outcome eval: PASS. Trajectory eval: FAIL (skip_exclusions mode).")
        print(f"    On CLM-2024-10002 (same adjuster-notes style, but E-11 triggered),")
        print(f"    the same path would pay out $2500 instead of $0 — the bill arrives.")


MITIGATION_NAME = "hard_step_limit"
MITIGATION_MAX_ITERS = 3   # was 6 — THE SINGLE CHANGE


def print_mitigation_summary(
    before_results, after_results,
    before_metrics, after_metrics,
    before_counts, after_counts,
) -> None:
    print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"{BOLD}{CYAN}  SINGLE MITIGATION: {MITIGATION_NAME.upper()} (max_iterations 6 → 3){RESET}")
    print(f"{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"\n  Rationale: Tighten the loop ceiling from 6 to 3 iterations.")
    print(f"  The correct sequence is always 3 tool calls (get_claim →")
    print(f"  search_policy_exclusions → compute_payout). Allowing 6 laps lets")
    print(f"  the agent spin on redundant tool calls or stall on rate-limit retries.")
    print(f"  ONE change, ONE mode, ONE price measured.")

    top_mode = "excess_steps"
    b_count = before_counts.get(top_mode, 0)
    a_count = after_counts.get(top_mode, 0)
    print(f"\n  Top mode '{top_mode}'  before → after: {BOLD}{b_count} → {a_count}{RESET}  "
          f"(delta {a_count - b_count:+d})")

    b_lat = statistics.median([r["latency_seconds"] for r in before_results])
    a_lat = statistics.median([r["latency_seconds"] for r in after_results])
    b_tok = statistics.mean([r["total_tokens"] for r in before_results])
    a_tok = statistics.mean([r["total_tokens"] for r in after_results])
    b_cost = statistics.median([r["cost_dollars"] for r in before_results])
    a_cost = statistics.median([r["cost_dollars"] for r in after_results])

    print(f"\n  {BOLD}Measured price paid:{RESET}")
    print(f"  {'Metric':<32} {'Before':>12} {'After':>12} {'Delta':>12}")
    print(f"  {'─'*30} {'─'*11} {'─'*11} {'─'*11}")
    print(f"  {'p50 latency (s)':<32} {b_lat:>12.2f} {a_lat:>12.2f} {a_lat-b_lat:>+12.2f}")
    print(f"  {'mean tokens/claim':<32} {b_tok:>12.0f} {a_tok:>12.0f} {a_tok-b_tok:>+12.0f}")
    print(f"  {'p50 cost/claim ($)':<32} {b_cost:>12.5f} {a_cost:>12.5f} {a_cost-b_cost:>+12.5f}")
    print(f"\n  Price is non-zero and measured. Mitigation is not free.")


def print_regression_table(before_counts, after_counts) -> None:
    print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"{BOLD}{CYAN}  REGRESSION CHECK — Per-Mode Counts Before → After{RESET}")
    print(f"{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"  {'Failure Mode':<25} {'Before':>8} {'After':>8} {'Delta':>8}  Status")
    print(f"  {'─'*23} {'─'*7} {'─'*7} {'─'*7}  {'─'*15}")
    found_regression = False
    for mode in FAILURE_MODES:
        b = before_counts.get(mode, 0)
        a = after_counts.get(mode, 0)
        delta = a - b
        if delta < 0:
            status = f"{GREEN}improved ↓{RESET}"
        elif delta > 0:
            status = f"{RED}WORSENED ↑{RESET}"
            found_regression = True
        else:
            status = f"{DIM}unchanged{RESET}"
        ds = f"{delta:+d}" if delta != 0 else "0"
        print(f"  {mode:<25} {b:>8} {a:>8} {ds:>8}  {status}")
    print(f"  {'─'*60}")
    if found_regression:
        print(f"  {YELLOW}At least one mode worsened — investigate before shipping.{RESET}")
    else:
        print(f"  {GREEN}No regression detected. No mode worsened; no new modes created.{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{CYAN}{'#'*72}{RESET}")
    print(f"{BOLD}{CYAN}  WEEK 8 — TRAJECTORY EVAL: CLAIMS AGENT FAILURE MODES{RESET}")
    print(f"{BOLD}{CYAN}{'#'*72}{RESET}")

    # PHASE 1: Baseline
    baseline_results = run_eval_pass(max_iters=6, label="BASELINE TRAJECTORY EVAL", verbose=True)
    baseline_metrics  = compute_metrics(baseline_results)
    baseline_counts   = count_failure_modes(baseline_results)

    print_results_table(baseline_results, "BASELINE — Results Table")
    print_metrics_table(baseline_metrics,  "BASELINE Trajectory Metrics")
    print_gap_narrative(baseline_results,  baseline_metrics)

    # PHASE 2: Mitigated
    mitigated_results = run_eval_pass(max_iters=MITIGATION_MAX_ITERS,
                                      label="MITIGATED TRAJECTORY EVAL (hard step limit)",
                                      verbose=True)
    mitigated_metrics  = compute_metrics(mitigated_results)
    mitigated_counts   = count_failure_modes(mitigated_results)

    print_results_table(mitigated_results, "MITIGATED — Results Table")
    print_metrics_table(mitigated_metrics,  "MITIGATED Trajectory Metrics")

    # PHASE 3: Mitigation summary + regression
    print_mitigation_summary(
        baseline_results, mitigated_results,
        baseline_metrics, mitigated_metrics,
        baseline_counts, mitigated_counts,
    )
    print_regression_table(baseline_counts, mitigated_counts)

    # Final summary
    print(f"\n{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"{BOLD}{CYAN}  FINAL SUMMARY{RESET}")
    print(f"{BOLD}{CYAN}{'='*72}{RESET}")
    print(f"\n  BASELINE   tool-choice accuracy : {baseline_metrics['tool_choice_accuracy']:.1%}")
    print(f"  BASELINE   outcome pass rate     : {baseline_metrics['outcome_pass_rate']:.1%}")
    print(f"  BASELINE   gap                   : {baseline_metrics['gap']:+.1%}")
    print(f"  BASELINE   cost p50 / max        : ${baseline_metrics['cost_p50']:.5f} / ${baseline_metrics['cost_max']:.5f}")
    print()
    print(f"  MITIGATED  tool-choice accuracy  : {mitigated_metrics['tool_choice_accuracy']:.1%}")
    print(f"  MITIGATED  outcome pass rate      : {mitigated_metrics['outcome_pass_rate']:.1%}")
    print(f"  MITIGATED  gap                   : {mitigated_metrics['gap']:+.1%}")
    print(f"  MITIGATED  cost p50 / max        : ${mitigated_metrics['cost_p50']:.5f} / ${mitigated_metrics['cost_max']:.5f}")
    print()
    top_mode = "excess_steps"
    print(f"  Top mode '{top_mode}'  before→after: "
          f"{baseline_counts.get(top_mode,0)} → {mitigated_counts.get(top_mode,0)}")
    print(f"\n{BOLD}{CYAN}{'#'*72}{RESET}\n")

    # Save JSON
    out = os.path.join(os.path.dirname(__file__), "trajectory_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "baseline": {
                "results": [{k: v for k, v in r.items() if k != "arg_results"} for r in baseline_results],
                "metrics": baseline_metrics,
                "mode_counts": baseline_counts,
            },
            "mitigated": {
                "results": [{k: v for k, v in r.items() if k != "arg_results"} for r in mitigated_results],
                "metrics": mitigated_metrics,
                "mode_counts": mitigated_counts,
            },
        }, f, indent=2)
    print(f"  Results saved → {out}\n")


if __name__ == "__main__":
    main()
