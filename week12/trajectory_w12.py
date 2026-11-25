"""
week12/trajectory_w12.py — Week 8 Trajectory Eval rewired to W12 integrated system.

Evaluates whether the agent follows the correct tool sequence for each claim type:

  All claims:   get_claim → check_coverage_in_force → (optional: search_policy_exclusions) → refer_to_adjuster
  Flood claims: MUST call search_policy_exclusions (not optional)
  Simple cases: MAY skip search_policy_exclusions

Covers 15 total claims:
  - 10 original Week 8 claims (CLM-2024-10001 through CLM-2024-10010)
  - 5 flood-straddle W12 claims (CLM-2024-77201..77203, CLM-2025-10001..10002)

Metrics:
  - tool_choice_accuracy:        % claims that follow an accepted sequence
  - outcome_vs_trajectory_gap:   referral_rate - trajectory_accuracy
  - flood_straddle_accuracy:     % of 5 straddle cases on correct path

NOTE: Week 8 trajectory eval is NOT yet fully rewired to live W12 agent calls
(ran-out-of-time — uses mock results). See seam_list.md item #10.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Tool names (must match MCP server tool registration)
# ---------------------------------------------------------------------------

GET_CLAIM = "get_claim"
CHECK_COVERAGE = "check_coverage_in_force"
SEARCH_EXCLUSIONS = "search_policy_exclusions"
REFER = "refer_to_adjuster"
COMPUTE_PAYOUT = "compute_payout"

# ---------------------------------------------------------------------------
# Expected tool sequences per claim
# ---------------------------------------------------------------------------
# Each claim has a list of *accepted* sequences. The agent's actual sequence
# must exactly match one of them (order matters).

EXPECTED_SEQUENCES: dict[str, dict] = {
    # --- Original 10 claims ---
    "CLM-2024-10001": {
        "description": "Pipe burst — sudden and accidental; no exclusion",
        "type": "simple",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10002": {
        "description": "Continuous seepage — E-11 exclusion applies",
        "type": "exclusion",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10003": {
        "description": "Named storm — NS deductible",
        "type": "storm",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, COMPUTE_PAYOUT, REFER],
        ],
    },
    "CLM-2024-10004": {
        "description": "Mold after pipe burst — sublimit applies",
        "type": "mold-covered",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
            [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],
        ],
    },
    "CLM-2024-10005": {
        "description": "Mold from humidity — E-22 exclusion",
        "type": "exclusion",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10006": {
        "description": "Roof hail damage — straightforward",
        "type": "simple",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10007": {
        "description": "Flood with prior seepage history — complex",
        "type": "flood",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10008": {
        "description": "Theft — valuation dispute",
        "type": "referral",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, REFER],
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10009": {
        "description": "Fire damage — garage endorsement ambiguity",
        "type": "referral",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, REFER],
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-10010": {
        "description": "Sewer backup — coverage depends on endorsement",
        "type": "exclusion",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    # --- 5 flood-straddle W12 claims ---
    # ALL must call check_coverage_in_force AND search_policy_exclusions
    "CLM-2024-77201": {
        "description": "Flood straddle 2024-12-30 — 2023 endorsement",
        "type": "flood-straddle",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-77202": {
        "description": "Flood straddle 2024-12-31 — 2023 endorsement (regression guard)",
        "type": "flood-straddle",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2024-77203": {
        "description": "Flood straddle 2024-12-29 — 2023 endorsement",
        "type": "flood-straddle",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2025-10001": {
        "description": "Flood straddle 2025-01-01 — 2025 endorsement (first day)",
        "type": "flood-straddle",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
    "CLM-2025-10002": {
        "description": "Flood straddle 2025-01-02 — 2025 endorsement",
        "type": "flood-straddle",
        "accepted": [
            [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],
        ],
    },
}

# ---------------------------------------------------------------------------
# Mock actual sequences (simulates W12 agent behavior)
# In production: replace with real trace retrieval from tracer.py / traces.jsonl
# ---------------------------------------------------------------------------

MOCK_ACTUAL_SEQUENCES: dict[str, list[str]] = {
    # --- Original 10 claims ---
    "CLM-2024-10001": [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],           # ✅ correct
    "CLM-2024-10002": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
    "CLM-2024-10003": [GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER],            # ✅ correct
    "CLM-2024-10004": [GET_CLAIM, CHECK_COVERAGE, REFER],                            # ❌ skipped exclusion search
    "CLM-2024-10005": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
    "CLM-2024-10006": [GET_CLAIM, GET_CLAIM, CHECK_COVERAGE, COMPUTE_PAYOUT, REFER], # ❌ excess_steps (duplicate get_claim)
    "CLM-2024-10007": [GET_CLAIM, SEARCH_EXCLUSIONS, CHECK_COVERAGE, REFER],         # ❌ wrong_tool_order (search before check)
    "CLM-2024-10008": [GET_CLAIM, CHECK_COVERAGE, REFER],                            # ✅ correct (referral, exclusion optional)
    "CLM-2024-10009": [GET_CLAIM, CHECK_COVERAGE, REFER],                            # ✅ correct
    "CLM-2024-10010": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
    # --- 5 flood-straddle W12 claims ---
    "CLM-2024-77201": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct (after fix)
    "CLM-2024-77202": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct (regression guard)
    "CLM-2024-77203": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
    "CLM-2025-10001": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
    "CLM-2025-10002": [GET_CLAIM, CHECK_COVERAGE, SEARCH_EXCLUSIONS, REFER],         # ✅ correct
}

# ---------------------------------------------------------------------------
# Sequence matcher
# ---------------------------------------------------------------------------


def sequence_matches(actual: list[str], accepted: list[list[str]]) -> bool:
    """Return True if actual exactly matches any accepted sequence."""
    return actual in accepted


def sequence_error_type(
    actual: list[str], accepted: list[list[str]], claim_type: str
) -> Optional[str]:
    """
    Classify the trajectory error mode if sequence does not match.

    Returns one of: 'skip_exclusions', 'wrong_tool_order', 'excess_steps', None.
    """
    # Excess steps: contains all required tools but extras inserted
    for acc in accepted:
        required_set = set(acc)
        actual_set = set(actual)
        if required_set.issubset(actual_set) and len(actual) > len(acc):
            return "excess_steps"

    # Wrong tool order: has the right tools but in wrong order
    for acc in accepted:
        if set(actual) == set(acc) and actual != acc:
            return "wrong_tool_order"

    # Skip exclusions: search_policy_exclusions missing when it should be present
    any_requires_search = any(SEARCH_EXCLUSIONS in acc for acc in accepted)
    if any_requires_search and SEARCH_EXCLUSIONS not in actual:
        return "skip_exclusions"

    return "other"


# ---------------------------------------------------------------------------
# Main trajectory eval runner
# ---------------------------------------------------------------------------


def run_trajectory_w12_eval(
    actual_sequences: Optional[dict[str, list[str]]] = None,
) -> dict:
    """
    Run W12 trajectory eval.

    Args:
        actual_sequences: {claim_number: [tool_calls]}. Defaults to MOCK_ACTUAL_SEQUENCES.

    Returns:
        {
          "total_claims": int,
          "tool_choice_accuracy": float,
          "referral_rate": float,
          "outcome_vs_trajectory_gap": float,
          "flood_straddle_accuracy": float,
          "mode_error_counts": dict,
          "results": list,
        }
    """
    if actual_sequences is None:
        actual_sequences = MOCK_ACTUAL_SEQUENCES

    results = []
    total = len(EXPECTED_SEQUENCES)
    correct = 0
    referral_count = 0
    straddle_correct = 0
    straddle_total = 0
    mode_errors: dict[str, int] = {}

    for claim_num, spec in EXPECTED_SEQUENCES.items():
        actual = actual_sequences.get(claim_num, [])
        accepted = spec["accepted"]
        claim_type = spec["type"]

        match = sequence_matches(actual, accepted)
        if match:
            correct += 1
            error_mode = None
        else:
            error_mode = sequence_error_type(actual, accepted, claim_type)
            if error_mode:
                mode_errors[error_mode] = mode_errors.get(error_mode, 0) + 1

        # Referral: does trajectory end with refer_to_adjuster?
        ends_with_referral = actual and actual[-1] == REFER
        if ends_with_referral:
            referral_count += 1

        # Flood straddle stats
        if claim_type == "flood-straddle":
            straddle_total += 1
            if match:
                straddle_correct += 1

        results.append(
            {
                "claim_number": claim_num,
                "description": spec["description"],
                "type": claim_type,
                "actual_sequence": actual,
                "accepted_sequences": accepted,
                "trajectory_correct": match,
                "ends_with_referral": ends_with_referral,
                "error_mode": error_mode,
            }
        )

    tool_choice_accuracy = correct / total if total else 0.0
    referral_rate = referral_count / total if total else 0.0
    outcome_vs_trajectory_gap = referral_rate - tool_choice_accuracy
    flood_accuracy = straddle_correct / straddle_total if straddle_total else 0.0

    return {
        "total_claims": total,
        "tool_choice_accuracy": round(tool_choice_accuracy, 4),
        "referral_rate": round(referral_rate, 4),
        "outcome_vs_trajectory_gap": round(outcome_vs_trajectory_gap, 4),
        "flood_straddle_accuracy": round(flood_accuracy, 4),
        "mode_error_counts": mode_errors,
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    print("=" * 70)
    print("W12 Trajectory Eval (Week 8 logic rewired to W12 integrated system)")
    print("NOTE: Using mock actual sequences — live agent wiring ran-out-of-time")
    print("      See seam_list.md item #10")
    print("=" * 70)

    out = run_trajectory_w12_eval()

    print(f"\nTotal claims evaluated:    {out['total_claims']}")
    print(f"Tool choice accuracy:       {out['tool_choice_accuracy']:.1%}")
    print(f"Referral rate:              {out['referral_rate']:.1%}")
    print(f"Outcome-vs-trajectory gap:  {out['outcome_vs_trajectory_gap']:.1%}")
    print(f"Flood-straddle accuracy:    {out['flood_straddle_accuracy']:.1%}")

    if out["mode_error_counts"]:
        print("\nError mode counts:")
        for mode, count in sorted(out["mode_error_counts"].items()):
            print(f"  {mode:<30s}: {count}")

    print("\nPer-claim results:")
    for r in out["results"]:
        icon = "✅" if r["trajectory_correct"] else "❌"
        err = f"  [{r['error_mode']}]" if r["error_mode"] else ""
        print(
            f"  {icon} {r['claim_number']:<20s} type={r['type']:<18s} "
            f"actual={r['actual_sequence']}{err}"
        )

    print()
    gap = out["outcome_vs_trajectory_gap"]
    print(
        f"⚠️  Gap ({gap:.1%}): The gap represents cases where the right information "
        "was surfaced but the wrong tool path was taken."
    )
    print(
        "   At flood-event volume (18,000 FNOLs), a 10% gap means 1,800 claims "
        "processed via wrong-path — if any of those skip check_coverage_in_force "
        "on a straddling loss date, they will apply the wrong endorsement."
    )

    out_path = Path(__file__).parent / "trajectory_results_w12.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nFull results written to: {out_path}")


if __name__ == "__main__":
    main()
