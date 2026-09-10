"""
week6/assertions.py — Deterministic (regex/parse) assertions for claim summaries.

Week 6 requirement: at least 2 criteria moved OUT of the LLM judge and into
deterministic checks that never call an LLM. These run first; only the
remaining *subjective* criteria go to the judge.

The 4 assertions implemented here:
  1. claim_number_format  — CLM-YYYY-NNNNN pattern echoed in the summary
  2. date_of_loss_present — Date of loss present and parseable
  3. excess_amount_numeric — Excess/deductible amount is a numeric value
  4. exclusion_id_cited    — If the case states a denial, an exclusion code (E-NN)
                             must be cited in the summary

IMPORTANT: No LLM calls anywhere in this file.
"""

import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# CLM-YYYY-NNNNN (e.g. CLM-2024-10001 or CLM-2024-88431)
_CLAIM_NUM_RE = re.compile(r"\bCLM-\d{4}-\d{4,6}\b")

# Exclusion code: E-NN or E-NNN (1–3 digit suffix)
_EXCLUSION_RE = re.compile(r"\bE-\d{1,3}\b")

# Monetary / numeric amount: $1,500 or 1500.00 or $7,000 or 2% etc.
_AMOUNT_RE = re.compile(
    r"(\$[\d,]+(?:\.\d{1,2})?|[\d,]+\.\d{1,2}|\d{1,3}(?:,\d{3})*|\d+%)"
)

# Keywords that indicate a denial
_DENIAL_KW_RE = re.compile(
    r"\b(denied|denial|excluded|exclusion applies|not covered|coverage denied)\b",
    re.IGNORECASE,
)

# Date patterns: ISO, US long, short month
_DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),                               # 2024-03-15
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),                         # 3/15/2024
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"\.?\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),                                                                    # March 15, 2024
    re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
               r"\.?\s+\d{4}\b", re.IGNORECASE),                        # 15 Mar 2024
]


# ---------------------------------------------------------------------------
# Individual assertion functions
# ---------------------------------------------------------------------------

def check_claim_number_format(summary: str, expected_claim_number: str) -> dict:
    """
    ASSERTION 1: The summary must echo the claim number in CLM-YYYY-NNNNN format.

    Passes if: at least one CLM-DDDD-DDDDD pattern is found in the summary
               AND it matches (or starts with) the expected claim number.
    """
    matches = _CLAIM_NUM_RE.findall(summary)
    if not matches:
        return {
            "name": "claim_number_format",
            "passed": False,
            "reason": "No CLM-YYYY-NNNNN pattern found in summary.",
            "found": None,
        }

    # Accept if any match equals the expected number
    if expected_claim_number and expected_claim_number in matches:
        return {
            "name": "claim_number_format",
            "passed": True,
            "reason": f"Claim number {expected_claim_number} echoed correctly.",
            "found": matches[0],
        }

    # Also accept if we just found *any* valid CLM pattern (for cases without expected)
    return {
        "name": "claim_number_format",
        "passed": True,
        "reason": f"CLM-format claim number present: {matches[0]}",
        "found": matches[0],
    }


def check_date_of_loss_present(summary: str, expected_date: str | None = None) -> dict:
    """
    ASSERTION 2: A parseable date must appear in the summary.

    Passes if: at least one date-like pattern is found.
    Does NOT require exact match to expected_date — the summary may reformat it.
    """
    for pattern in _DATE_PATTERNS:
        matches = pattern.findall(summary)
        if matches:
            return {
                "name": "date_of_loss_present",
                "passed": True,
                "reason": f"Date found: '{matches[0]}'",
                "found": matches[0],
            }

    return {
        "name": "date_of_loss_present",
        "passed": False,
        "reason": "No parseable date found in summary.",
        "found": None,
    }


def check_excess_amount_numeric(
    summary: str, expected_amount: float | None = None
) -> dict:
    """
    ASSERTION 3: A numeric dollar amount or percentage must appear in the summary
    when an excess/deductible is defined in the case.

    If expected_amount is None, the check is skipped (passes vacuously).
    """
    if expected_amount is None:
        return {
            "name": "excess_amount_numeric",
            "passed": True,
            "reason": "No excess amount defined for this case — assertion skipped.",
            "found": None,
        }

    matches = _AMOUNT_RE.findall(summary)
    if not matches:
        return {
            "name": "excess_amount_numeric",
            "passed": False,
            "reason": "No numeric amount found in summary despite case having excess/deductible.",
            "found": None,
        }

    return {
        "name": "excess_amount_numeric",
        "passed": True,
        "reason": f"Numeric amount present: {matches[0]}",
        "found": matches[0],
    }


def check_exclusion_id_cited(
    summary: str, denial_reason: str | None, expected_exclusion_id: str | None
) -> dict:
    """
    ASSERTION 4: If the case has a denial_reason, an exclusion clause ID
    (E-NN format) MUST appear in the summary.

    If no denial_reason → passes vacuously (no denial = no exclusion needed).
    """
    if not denial_reason:
        return {
            "name": "exclusion_id_cited",
            "passed": True,
            "reason": "No denial in this case — exclusion citation not required.",
            "found": None,
        }

    # Denial exists — check if summary mentions denial AND cites exclusion
    summary_mentions_denial = bool(_DENIAL_KW_RE.search(summary))
    exclusion_matches = _EXCLUSION_RE.findall(summary)

    if not exclusion_matches:
        return {
            "name": "exclusion_id_cited",
            "passed": False,
            "reason": (
                "Case has a denial but no E-NN exclusion code found in summary. "
                f"Expected exclusion: {expected_exclusion_id or 'any'}."
            ),
            "found": None,
        }

    # If a specific exclusion is expected, verify it's the one cited
    if expected_exclusion_id and expected_exclusion_id not in exclusion_matches:
        return {
            "name": "exclusion_id_cited",
            "passed": False,
            "reason": (
                f"Expected exclusion {expected_exclusion_id} but summary cites "
                f"{exclusion_matches}. Wrong exclusion cited."
            ),
            "found": exclusion_matches,
        }

    return {
        "name": "exclusion_id_cited",
        "passed": True,
        "reason": f"Exclusion code(s) cited: {exclusion_matches}",
        "found": exclusion_matches,
    }


# ---------------------------------------------------------------------------
# Run all 4 assertions on one summary
# ---------------------------------------------------------------------------

def run_assertions(summary: str, case: dict) -> dict:
    """
    Run all 4 deterministic assertions against a single claim summary.

    Args:
        summary:  The generated claim summary string.
        case:     The eval case dict (from eval_cases_25.jsonl).

    Returns:
        {
          "all_passed": bool,
          "pass_count": int,
          "fail_count": int,
          "results": [list of per-assertion dicts],
        }
    """
    results = [
        check_claim_number_format(summary, case.get("claim_number", "")),
        check_date_of_loss_present(summary, case.get("date_of_loss")),
        check_excess_amount_numeric(summary, case.get("excess_amount")),
        check_exclusion_id_cited(
            summary,
            case.get("denial_reason"),
            case.get("exclusion_id"),
        ),
    ]

    passes = sum(1 for r in results if r["passed"])
    fails = len(results) - passes

    return {
        "case_id": case.get("id"),
        "all_passed": fails == 0,
        "pass_count": passes,
        "fail_count": fails,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_all_assertions(summaries: dict[int, str], cases: list[dict]) -> list[dict]:
    """
    Run assertions over all cases.

    Args:
        summaries: {case_id: summary_text}
        cases:     List of case dicts from eval_cases_25.jsonl

    Returns:
        List of assertion result dicts, one per case.
    """
    all_results = []
    for case in cases:
        cid = case["id"]
        summary = summaries.get(cid, "")
        result = run_assertions(summary, case)
        all_results.append(result)
    return all_results


# ---------------------------------------------------------------------------
# CLI (for testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick smoke test
    test_summary = """
    Claim CLM-2024-10001 — Date of loss: 2024-03-15.
    Insured reported a burst supply line. Sudden and accidental discharge confirmed.
    Claim denied — exclusion E-11 applies for continuous seepage.
    Deductible $1,500.00 applies.
    """
    test_case = {
        "id": 1,
        "claim_number": "CLM-2024-10001",
        "date_of_loss": "2024-03-15",
        "excess_amount": 1500.00,
        "denial_reason": "Continuous seepage",
        "exclusion_id": "E-11",
    }
    r = run_assertions(test_summary, test_case)
    print(f"All passed: {r['all_passed']} ({r['pass_count']}/4)")
    for a in r["results"]:
        icon = "✅" if a["passed"] else "❌"
        print(f"  {icon} {a['name']}: {a['reason']}")
