"""
policy_data.py — Week 12 Capstone: Policy-in-force data and endorsement versioning.

Provides:
  - ENDORSEMENT_VERSIONS: 2023 and 2025 endorsement sets with flood exclusion wording
  - POLICY_IN_FORCE: active date ranges per policy number
  - DEDUCTIBLE_TABLE: deductible / sub_limit / policy_limit as THREE DISTINCT numbers
  - FLOOD_STRADDLE_CLAIMS: 5 bonus eval claims straddling the 2025 endorsement boundary
  - Functions: get_endorsement_set_for_loss_date, check_coverage_in_force, get_deductible_info
"""

from datetime import date
from typing import Dict, Any, Optional


# ---------------------------------------------------------------------------
# Endorsement version wording
# ---------------------------------------------------------------------------

ENDORSEMENT_VERSIONS: Dict[str, Dict[str, Any]] = {
    "2023": {
        "effective_from": "2023-01-01",
        "effective_to": "2024-12-31",
        "flood_exclusion_clause": "FL-3",
        "flood_exclusion_code": "E-28",
        "flood_exclusion_wording": (
            "CLAUSE FL-3 [ENDORSEMENT 2023]: Flood damage is excluded when sustained "
            "precipitation exceeds the 24-hour threshold defined in the Schedule of "
            "Perils. Surface water ingress from events below that threshold may be "
            "considered under the base policy water damage provisions. See exclusion "
            "table E-28."
        ),
        "flood_exclusion_summary": "Flood excluded when 24-hour precipitation threshold exceeded (FL-3, E-28).",
        "note": "2023 wording requires threshold breach — shorter events may not trigger exclusion.",
    },
    "2025": {
        "effective_from": "2025-01-01",
        "effective_to": None,  # currently in force
        "flood_exclusion_clause": "FL-3A",
        "flood_exclusion_code": "E-28A",
        "flood_exclusion_wording": (
            "CLAUSE FL-3A (Rev 2025) [ENDORSEMENT 2025]: Flood damage is excluded when "
            "any precipitation-driven surface water ingress occurs, regardless of event "
            "duration, volume, or threshold. The 24-hour threshold concept from the prior "
            "endorsement (FL-3) no longer applies. See exclusion table E-28A."
        ),
        "flood_exclusion_summary": "Flood excluded for ANY precipitation-driven surface water ingress (FL-3A, E-28A). No threshold.",
        "note": "2025 wording is broader — eliminates the duration threshold, covering all precipitation-driven ingress.",
    },
}


# ---------------------------------------------------------------------------
# Policy in-force table
# ---------------------------------------------------------------------------

POLICY_IN_FORCE: Dict[str, Dict[str, Any]] = {
    # Original 10 policies (all 2024 losses → 2023 endorsement set)
    "POL-HO-772101": {"policy_number": "POL-HO-772101", "product": "homeowners", "inception_date": "2023-01-01", "expiry_date": "2025-12-31", "endorsement_set": "2023"},
    "POL-HO-772102": {"policy_number": "POL-HO-772102", "product": "homeowners", "inception_date": "2023-01-01", "expiry_date": "2025-12-31", "endorsement_set": "2023"},
    "POL-HO-772103": {"policy_number": "POL-HO-772103", "product": "homeowners", "inception_date": "2023-03-01", "expiry_date": "2025-02-28", "endorsement_set": "2023"},
    "POL-HO-772104": {"policy_number": "POL-HO-772104", "product": "homeowners", "inception_date": "2023-04-01", "expiry_date": "2025-03-31", "endorsement_set": "2023"},
    "POL-HO-772105": {"policy_number": "POL-HO-772105", "product": "homeowners", "inception_date": "2023-04-01", "expiry_date": "2025-03-31", "endorsement_set": "2023"},
    "POL-HO-772106": {"policy_number": "POL-HO-772106", "product": "homeowners", "inception_date": "2023-05-01", "expiry_date": "2025-04-30", "endorsement_set": "2023"},
    "POL-HO-772107": {"policy_number": "POL-HO-772107", "product": "homeowners", "inception_date": "2023-05-01", "expiry_date": "2025-04-30", "endorsement_set": "2023"},
    "POL-HO-772108": {"policy_number": "POL-HO-772108", "product": "homeowners", "inception_date": "2023-05-01", "expiry_date": "2025-04-30", "endorsement_set": "2023"},
    "POL-HO-772109": {"policy_number": "POL-HO-772109", "product": "homeowners", "inception_date": "2023-01-01", "expiry_date": "2025-12-31", "endorsement_set": "2023"},
    "POL-HO-772110": {"policy_number": "POL-HO-772110", "product": "homeowners", "inception_date": "2023-05-01", "expiry_date": "2025-04-30", "endorsement_set": "2023"},
    # Flood-straddle policies (5 bonus cases)
    "POL-HO-772201": {"policy_number": "POL-HO-772201", "product": "homeowners", "inception_date": "2023-01-01", "expiry_date": "2025-06-30", "endorsement_set": "2023"},
    "POL-HO-772202": {"policy_number": "POL-HO-772202", "product": "homeowners", "inception_date": "2024-06-01", "expiry_date": "2026-05-31", "endorsement_set": "2023"},
    "POL-HO-772203": {"policy_number": "POL-HO-772203", "product": "homeowners", "inception_date": "2025-01-01", "expiry_date": "2026-12-31", "endorsement_set": "2025"},
    "POL-HO-772204": {"policy_number": "POL-HO-772204", "product": "homeowners", "inception_date": "2024-12-31", "expiry_date": "2025-12-30", "endorsement_set": "2023"},
    "POL-HO-772205": {"policy_number": "POL-HO-772205", "product": "homeowners", "inception_date": "2025-01-01", "expiry_date": "2026-01-01", "endorsement_set": "2025"},
}


# ---------------------------------------------------------------------------
# Deductible / sub_limit / policy_limit table (THREE DISTINCT NUMBERS)
# ---------------------------------------------------------------------------

DEDUCTIBLE_TABLE: Dict[str, Dict[str, Any]] = {
    "POL-HO-772101": {"deductible": 1500.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772102": {"deductible": 2000.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772103": {"deductible": 5000.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772104": {"deductible": 1000.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772105": {"deductible": 750.00,  "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772106": {"deductible": 500.00,  "flood_sublimit": 25000.00, "policy_limit": 350000.00},
    "POL-HO-772107": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772108": {"deductible": 1000.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772109": {"deductible": 1000.00, "flood_sublimit": 50000.00, "policy_limit": 350000.00},
    "POL-HO-772110": {"deductible": 500.00,  "flood_sublimit": 25000.00, "policy_limit": 350000.00},
    "POL-HO-772201": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 400000.00},
    "POL-HO-772202": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 400000.00},
    "POL-HO-772203": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 400000.00},
    "POL-HO-772204": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 400000.00},
    "POL-HO-772205": {"deductible": 2500.00, "flood_sublimit": 50000.00, "policy_limit": 400000.00},
}


# ---------------------------------------------------------------------------
# Flood straddle claims (bonus eval cases)
# ---------------------------------------------------------------------------

FLOOD_STRADDLE_CLAIMS: Dict[str, Dict[str, Any]] = {
    "CLM-2024-77201": {
        "claim_id": "CLM-2024-77201",
        "policy_number": "POL-HO-772201",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-08-15",
        "claimed_amount": 28000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Surface water ingress from sustained precipitation event dated 2024-08-15. "
            "Event duration approximately 36 hours, exceeding 24-hour threshold defined "
            "in Schedule of Perils. Basement flooding confirmed. "
            "Policy form HO-0304. Loss date falls within 2023 endorsement period. "
            "Endorsement 2023 FL-3 applies. Adjuster to verify threshold breach."
        ),
        "expected_endorsement_set": "2023",
        "expected_exclusion_clause": "FL-3",
        "expected_exclusion_code": "E-28",
        "expected_referral": True,
        "description": "Flood loss Aug 2024 — 2023 FL-3 applies (threshold-based).",
    },
    "CLM-2024-77202": {
        "claim_id": "CLM-2024-77202",
        "policy_number": "POL-HO-772202",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-12-31",
        "claimed_amount": 32000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Flood loss on 2024-12-31 — last day of 2023 endorsement period. "
            "2023 endorsement applies: CLAUSE FL-3 requires 24-hour threshold breach. "
            "36-hour sustained precipitation confirmed. "
            "Do NOT apply 2025 FL-3A wording — not in force on loss date."
        ),
        "expected_endorsement_set": "2023",
        "expected_exclusion_clause": "FL-3",
        "expected_exclusion_code": "E-28",
        "expected_referral": True,
        "description": "Flood loss on 2024-12-31 — LAST day of 2023 endorsement. Classic straddle.",
    },
    "CLM-2025-77203": {
        "claim_id": "CLM-2025-77203",
        "policy_number": "POL-HO-772203",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2025-03-10",
        "claimed_amount": 41000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Flood loss on 2025-03-10. Policy inception 2025-01-01. 2025 endorsement applies. "
            "CLAUSE FL-3A: any precipitation-driven surface water ingress excluded. No threshold."
        ),
        "expected_endorsement_set": "2025",
        "expected_exclusion_clause": "FL-3A",
        "expected_exclusion_code": "E-28A",
        "expected_referral": True,
        "description": "Flood loss post-2025 — FL-3A (broader) applies.",
    },
    "CLM-2024-77204": {
        "claim_id": "CLM-2024-77204",
        "policy_number": "POL-HO-772204",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2024-12-31",
        "claimed_amount": 19000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Loss date one day before 2025 endorsement boundary. Policy inception 2024-12-31. "
            "2023 endorsement applies on loss date. Must apply FL-3 threshold-based wording."
        ),
        "expected_endorsement_set": "2023",
        "expected_exclusion_clause": "FL-3",
        "expected_exclusion_code": "E-28",
        "expected_referral": True,
        "description": "Loss date = inception date = 2024-12-31. 2023 endorsement.",
    },
    "CLM-2025-77205": {
        "claim_id": "CLM-2025-77205",
        "policy_number": "POL-HO-772205",
        "form_number": "HO-0304",
        "edition_date": "03-24",
        "date_of_loss": "2025-01-01",
        "claimed_amount": 22000.00,
        "excess_amount": 2500.00,
        "adjuster_notes": (
            "Loss date 2025-01-01, first day of 2025 endorsement. FL-3A applies. "
            "Any precipitation-driven surface water ingress is excluded."
        ),
        "expected_endorsement_set": "2025",
        "expected_exclusion_clause": "FL-3A",
        "expected_exclusion_code": "E-28A",
        "expected_referral": True,
        "description": "Loss date = 2025-01-01, FIRST day of 2025 endorsement. FL-3A.",
    },
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _parse_date(d: str) -> date:
    """Parse ISO date string to date object."""
    return date.fromisoformat(d)


def get_endorsement_set_for_loss_date(policy_number: str, loss_date: str) -> str:
    """
    Return the endorsement set ("2023" or "2025") in force on the given loss date.
    This is a DATE FILTER enforced in code, NOT a prompt hint.
    """
    policy = POLICY_IN_FORCE.get(policy_number)
    if not policy:
        raise ValueError(
            f"Policy '{policy_number}' not found in POLICY_IN_FORCE table. "
            f"Cannot determine endorsement set for loss date {loss_date}."
        )
    return policy["endorsement_set"]


def get_flood_exclusion_wording(endorsement_set: str) -> Dict[str, Any]:
    """Return the flood exclusion wording dict for the given endorsement set."""
    if endorsement_set not in ENDORSEMENT_VERSIONS:
        raise ValueError(
            f"Unknown endorsement set '{endorsement_set}'. "
            f"Valid sets: {list(ENDORSEMENT_VERSIONS.keys())}"
        )
    return ENDORSEMENT_VERSIONS[endorsement_set]


def check_coverage_in_force(policy_number: str, loss_date: str) -> Dict[str, Any]:
    """
    Check whether coverage was in force on the loss date and return the endorsement set.

    Returns the endorsement set that MUST be used for all subsequent citations.
    Also returns deductible, flood_sublimit, and policy_limit as THREE DISTINCT numbers.
    """
    policy = POLICY_IN_FORCE.get(policy_number)
    if not policy:
        raise ValueError(
            f"Policy '{policy_number}' not found. "
            f"Cannot determine coverage-in-force for loss date {loss_date}."
        )

    inception = _parse_date(policy["inception_date"])
    expiry = _parse_date(policy["expiry_date"])
    loss = _parse_date(loss_date)
    in_force = inception <= loss <= expiry

    endorse_set = policy["endorsement_set"]
    end_version = ENDORSEMENT_VERSIONS[endorse_set]

    # Get deductible table info
    ded_info = DEDUCTIBLE_TABLE.get(policy_number, {})

    if in_force:
        reason = (
            f"Policy {policy_number} was in force on {loss_date} "
            f"(inception {policy['inception_date']}, expiry {policy['expiry_date']}). "
            f"Endorsement set '{endorse_set}' applies. "
            f"Flood exclusion: {end_version['flood_exclusion_clause']} ({end_version['flood_exclusion_code']})."
        )
    else:
        reason = (
            f"Policy {policy_number} was NOT in force on {loss_date}. "
            f"Policy period: {policy['inception_date']} to {policy['expiry_date']}. "
            f"Loss date {loss_date} falls outside this period. "
            f"Refer to adjuster: no coverage basis for this loss date."
        )

    return {
        "in_force": in_force,
        "policy_number": policy_number,
        "endorsement_set": endorse_set,
        "inception_date": policy["inception_date"],
        "expiry_date": policy["expiry_date"],
        "flood_exclusion_clause": end_version["flood_exclusion_clause"],
        "flood_exclusion_code": end_version["flood_exclusion_code"],
        "flood_exclusion_summary": end_version["flood_exclusion_summary"],
        "flood_exclusion_wording": end_version["flood_exclusion_wording"],
        # THREE DISTINCT NUMBERS — never conflate
        "deductible": ded_info.get("deductible"),
        "flood_sublimit": ded_info.get("flood_sublimit"),
        "policy_limit": ded_info.get("policy_limit"),
        "reason": reason,
    }


def get_deductible_info(policy_number: str) -> Dict[str, Any]:
    """
    Return deductible, flood_sublimit, and policy_limit as THREE DISTINCT numbers.
    """
    if policy_number not in DEDUCTIBLE_TABLE:
        return {
            "error": f"Policy '{policy_number}' not in deductible table.",
            "deductible": None,
            "flood_sublimit": None,
            "policy_limit": None,
        }
    info = DEDUCTIBLE_TABLE[policy_number]
    return {
        "policy_number": policy_number,
        "deductible": info["deductible"],
        "flood_sublimit": info["flood_sublimit"],
        "policy_limit": info["policy_limit"],
        "note": (
            "These are three separate figures: "
            "deductible (insured bears first), "
            "flood_sublimit (max payout for flood perils), "
            "policy_limit (total coverage cap). "
            "Never report only one of these for flood claims."
        ),
    }
