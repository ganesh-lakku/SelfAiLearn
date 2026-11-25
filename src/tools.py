"""
tools.py — Unified toolset for Insurance Claims Triage (Agent and Fixed Workflow).

Requirements satisfied:
1. Third tool added: `compute_payout`
   - Single distinct responsibility: calculate net payable payout after policy excess.
   - Uses an enum for the claim-status parameter: ClaimStatus (COVERED, DENIED, PARTIALLY_COVERED).
   - Zero description overlap across the 3 tools:
     - get_claim: "Retrieve claim record and adjuster notes by claim number."
     - search_policy_exclusions: "Search policy endorsement documentation for coverage exclusions and limitations matching a peril or cause of loss."
     - compute_payout: "Calculate net payable claim amount by deducting excess from claimed amount based on the claim coverage status."
2. Supports OpenAI-compatible function schema formatting.
3. Provides deterministic tool dispatcher.

Week 12 additions:
4. check_coverage_in_force: Verify which endorsement set was in force on the loss date.
5. refer_to_adjuster: Refer claim to a human adjuster; never makes a coverage decision.
"""

import os
import sys
from enum import Enum
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from claims_data import get_claim_by_id
from tracer import redact
from policy_data import (
    check_coverage_in_force as _check_cif,
    get_endorsement_set_for_loss_date,
    get_deductible_info,
    get_flood_exclusion_wording,
    FLOOD_STRADDLE_CLAIMS,
)

# Import hybrid search if available, fallback to vector search or raw text search
try:
    from hybrid_retrieval import hybrid_search
    RETRIEVAL_AVAILABLE = True
except Exception:
    try:
        from retrieval import search as vector_search
        RETRIEVAL_AVAILABLE = True
    except Exception:
        RETRIEVAL_AVAILABLE = False


class ClaimStatus(str, Enum):
    """Enumeration of valid claim coverage statuses."""
    COVERED = "COVERED"
    DENIED = "DENIED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"


# ---------------------------------------------------------------------------
# Tool 1: get_claim
# ---------------------------------------------------------------------------
def get_claim(claim_id: str) -> Dict[str, Any]:
    """Retrieve claim record and adjuster notes by claim number."""
    cid = claim_id.strip()
    claim = None
    try:
        claim = get_claim_by_id(cid)
    except KeyError:
        if cid in FLOOD_STRADDLE_CLAIMS:
            claim = FLOOD_STRADDLE_CLAIMS[cid]

    if claim:
        return {
            "success": True,
            "claim_id": claim["claim_id"],
            "policy_number": claim["policy_number"],
            "form_number": claim["form_number"],
            "edition_date": claim.get("edition_date", ""),
            "date_of_loss": claim["date_of_loss"],
            "claimed_amount": claim["claimed_amount"],
            "excess_amount": claim.get("excess_amount", 0.0),
            "adjuster_notes": redact(claim["adjuster_notes"]),
        }
    return {
        "success": False,
        "error": f"Claim ID '{claim_id}' does not exist in claims records."
    }


# ---------------------------------------------------------------------------
# Tool 2: search_policy_exclusions
# ---------------------------------------------------------------------------
def search_policy_exclusions(policy_form: str, query: str, endorsement_version: Optional[str] = None) -> Dict[str, Any]:
    """
    Search policy endorsement documentation for coverage exclusions and limitations
    matching a peril or cause of loss.
    """
    q_lower = query.lower()
    search_query = f"{policy_form} {query}".strip()

    hits = []

    # Dedicated handler for flood exclusions (Week 12 endorsement versioning)
    if any(k in q_lower for k in ["flood", "precipitation", "surface water", "water ingress", "fl-3", "e-28"]):
        target_version = endorsement_version
        if not target_version:
            if "2025" in query:
                target_version = "2025"
            elif "2023" in query:
                target_version = "2023"
            else:
                target_version = "2023"

        flood_info = get_flood_exclusion_wording(target_version)
        hits.append({
            "chunk_id": f"{policy_form}-FL-EXCL-{target_version}",
            "form_number": policy_form,
            "clause_id": flood_info["flood_exclusion_clause"],
            "exclusion_code": flood_info["flood_exclusion_code"],
            "endorsement_set": target_version,
            "text": flood_info["flood_exclusion_wording"],
        })

    # Attempt vector/hybrid search first
    if RETRIEVAL_AVAILABLE:
        try:
            from hybrid_retrieval import hybrid_search
            raw_hits = hybrid_search(search_query, n_results=4)
            for h in raw_hits:
                hits.append({
                    "chunk_id": h["chunk_id"],
                    "form_number": h["metadata"].get("form_number", policy_form),
                    "clause_id": h["metadata"].get("clause_id", ""),
                    "text": h["text"][:300]
                })
        except Exception:
            pass

    # Fallback/supplement: read endorsement files directly if hits empty
    if not hits:
        endorsements_dir = os.path.join(os.path.dirname(__file__), "..", "endorsements")
        if os.path.isdir(endorsements_dir):
            for fname in os.listdir(endorsements_dir):
                if policy_form.lower().replace("-", "") in fname.lower().replace("-", ""):
                    fpath = os.path.join(endorsements_dir, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    hits.append({
                        "chunk_id": f"{policy_form}-doc",
                        "form_number": policy_form,
                        "clause_id": "FULL-TEXT",
                        "text": text[:800]
                    })
                    break

    return {
        "success": True,
        "policy_form": policy_form,
        "query": query,
        "matching_clauses_count": len(hits),
        "results": hits
    }


# ---------------------------------------------------------------------------
# Tool 3: compute_payout (Third Tool)
# ---------------------------------------------------------------------------
def compute_payout(claimed_amount: float, excess_amount: float, status: str) -> Dict[str, Any]:
    """
    Calculate net payable claim amount by deducting excess from claimed amount
    based on the claim coverage status.
    """
    # Validate and normalize enum
    try:
        validated_status = ClaimStatus(status.upper().strip())
    except (ValueError, AttributeError):
        return {
            "success": False,
            "error": f"Invalid claim status '{status}'. Must be one of {[s.value for s in ClaimStatus]}."
        }

    claimed = max(0.0, float(claimed_amount))
    excess = max(0.0, float(excess_amount))

    if validated_status == ClaimStatus.DENIED:
        payable = 0.0
        reason = "Claim is denied under policy exclusions; payable amount is $0.00."
    elif validated_status == ClaimStatus.COVERED:
        payable = max(0.0, round(claimed - excess, 2))
        if claimed <= excess:
            reason = f"Covered loss (${claimed:.2f}) does not exceed excess (${excess:.2f}); payable amount is $0.00."
        else:
            reason = f"Covered loss (${claimed:.2f}) less excess (${excess:.2f}) leaves payable amount ${payable:.2f}."
    elif validated_status == ClaimStatus.PARTIALLY_COVERED:
        # If partially covered, calculate standard deduction
        payable = max(0.0, round(claimed - excess, 2))
        reason = f"Partially covered loss (${claimed:.2f}) less excess (${excess:.2f}) leaves payable amount ${payable:.2f}."

    return {
        "success": True,
        "status": validated_status.value,
        "claimed_amount": round(claimed, 2),
        "excess_amount": round(excess, 2),
        "payable_amount": payable,
        "calculation_summary": reason
    }


# ---------------------------------------------------------------------------
# Tool 4 (Week 12): check_coverage_in_force
# ---------------------------------------------------------------------------
def check_coverage_in_force(policy_number: str, loss_date: str) -> Dict[str, Any]:
    """
    Verify which endorsement set was in force on the loss date for a given policy.

    IMPORTANT: Call this tool BEFORE retrieving any exclusion wording.
    The endorsement version returned here determines which wording applies.
    NEVER apply current/latest wording without verifying the loss date first.

    Returns deductible, flood sub-limit, and policy limit as DISTINCT fields.
    """
    try:
        cif = _check_cif(policy_number=policy_number, loss_date=loss_date)
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    # Deductible info
    try:
        ded_info = get_deductible_info(policy_number)
    except KeyError:
        ded_info = {"deductible": None, "flood_sublimit": None, "policy_limit": None}

    # Flood exclusion wording summary for the applicable endorsement set
    eset = cif.get("endorsement_set", "UNKNOWN")
    try:
        flood_wording = get_flood_exclusion_wording(eset)
        clause_summary = (
            f"{flood_wording['flood_exclusion_clause']} | "
            f"Endorsement set {eset} | "
            f"Effective {flood_wording['effective_from']} to "
            f"{flood_wording['effective_to'] or 'present'}"
        )
    except (KeyError, Exception):
        clause_summary = f"Flood exclusion wording unavailable for endorsement_set '{eset}'."

    return {
        "success":                       True,
        "in_force":                      cif["in_force"],
        "endorsement_set":               eset,
        "inception_date":                cif["inception_date"],
        "expiry_date":                   cif["expiry_date"],
        "flood_exclusion_wording_summary": clause_summary,
        "deductible":                    ded_info["deductible"],
        "flood_sublimit":                ded_info["flood_sublimit"],
        "policy_limit":                  ded_info["policy_limit"],
        "reason":                        cif["reason"],
    }


# ---------------------------------------------------------------------------
# Tool 5 (Week 12): refer_to_adjuster
# ---------------------------------------------------------------------------
def refer_to_adjuster(
    claim_id: str,
    reason: str,
    citations: List[str],
    endorsement_version: str,
    loss_date: str,
) -> Dict[str, Any]:
    """
    Refer a claim to a human adjuster for coverage determination.

    This tool does NOT make a coverage decision.
    It surfaces the facts, citations, and endorsement version for human review.
    NEVER returns a 'covered' or 'denied' verdict — always refers.
    """
    return {
        "success":                   True,
        "action":                    "REFER_TO_ADJUSTER",
        "claim_id":                  claim_id,
        "referral_reason":           reason,
        "citations":                 citations,
        "endorsement_version_applied": endorsement_version,
        "loss_date":                 loss_date,
        "message":                   "Claim referred to human adjuster for coverage determination.",
    }


# ---------------------------------------------------------------------------
# OpenAI Tool Specifications
# ---------------------------------------------------------------------------
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_claim",
            "description": "Retrieve claim record and adjuster notes by claim number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": "The unique claim identifier, e.g. 'CLM-2024-10001'."
                    }
                },
                "required": ["claim_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy_exclusions",
            "description": "Search policy endorsement documentation for coverage exclusions and limitations matching a peril or cause of loss.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_form": {
                        "type": "string",
                        "description": "The policy endorsement form number, e.g. 'HO-0304', 'HO-0308'."
                    },
                    "query": {
                        "type": "string",
                        "description": "The peril, cause of loss, or exclusion keyword to search for, e.g. 'continuous seepage', 'earthquake tremors', 'business pursuits'."
                    }
                },
                "required": ["policy_form", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compute_payout",
            "description": "Calculate net payable claim amount by deducting excess from claimed amount based on the claim coverage status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claimed_amount": {
                        "type": "number",
                        "description": "Total claimed repair or loss amount in dollars."
                    },
                    "excess_amount": {
                        "type": "number",
                        "description": "Policy deductible / excess amount in dollars."
                    },
                    "status": {
                        "type": "string",
                        "enum": ["COVERED", "DENIED", "PARTIALLY_COVERED"],
                        "description": "The coverage determination status."
                    }
                },
                "required": ["claimed_amount", "excess_amount", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_coverage_in_force",
            "description": (
                "Call this tool to verify which endorsement set was in force on the loss date "
                "BEFORE retrieving any exclusion wording. The endorsement version returned "
                "determines which wording to apply. NEVER apply current/latest wording without "
                "verifying the loss date first. Returns deductible, flood_sublimit, and "
                "policy_limit as three distinct fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_number": {
                        "type": "string",
                        "description": "The policy number, e.g. 'POL-HO-772101'."
                    },
                    "loss_date": {
                        "type": "string",
                        "description": "The date of loss in ISO-8601 format YYYY-MM-DD, e.g. '2024-08-15'."
                    }
                },
                "required": ["policy_number", "loss_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "refer_to_adjuster",
            "description": (
                "ALWAYS use this as the final step. This system does NOT make coverage decisions "
                "— it only surfaces facts and refers to a human adjuster. Never emit the word "
                "'covered' or 'denied' as a final verdict. Always refer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": "The claim identifier being referred."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for referral to the human adjuster."
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of policy clause citations in format [CLAUSE clause_id | ENDORSEMENT endorsement_set | LOSS DATE loss_date]."
                    },
                    "endorsement_version": {
                        "type": "string",
                        "description": "The endorsement set version applied, e.g. '2023' or '2025'."
                    },
                    "loss_date": {
                        "type": "string",
                        "description": "The date of loss in ISO-8601 format YYYY-MM-DD."
                    }
                },
                "required": ["claim_id", "reason", "citations", "endorsement_version", "loss_date"]
            }
        }
    },
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute tool by name and return result dictionary."""
    if tool_name == "get_claim":
        return get_claim(arguments.get("claim_id", ""))
    elif tool_name == "search_policy_exclusions":
        return search_policy_exclusions(
            policy_form=arguments.get("policy_form", ""),
            query=arguments.get("query", ""),
            endorsement_version=arguments.get("endorsement_version"),
        )
    elif tool_name == "compute_payout":
        return compute_payout(
            claimed_amount=arguments.get("claimed_amount", 0.0),
            excess_amount=arguments.get("excess_amount", 0.0),
            status=arguments.get("status", "DENIED")
        )
    elif tool_name == "check_coverage_in_force":
        return check_coverage_in_force(
            policy_number=arguments.get("policy_number", ""),
            loss_date=arguments.get("loss_date", ""),
        )
    elif tool_name == "refer_to_adjuster":
        return refer_to_adjuster(
            claim_id=arguments.get("claim_id", ""),
            reason=arguments.get("reason", ""),
            citations=arguments.get("citations", []),
            endorsement_version=arguments.get("endorsement_version", ""),
            loss_date=arguments.get("loss_date", ""),
        )
    else:
        return {"success": False, "error": f"Unknown tool name '{tool_name}'."}


def get_third_tool_diff() -> str:
    """Returns the diff showing the addition of compute_payout with enum parameters."""
    return '''diff --git a/src/tools.py b/src/tools.py
--- a/src/tools.py (Week 6: 2 tools)
+++ b/src/tools.py (Week 7: 3 tools)
@@ -0,0 +1,35 @@
+class ClaimStatus(str, Enum):
+    COVERED = "COVERED"
+    DENIED = "DENIED"
+    PARTIALLY_COVERED = "PARTIALLY_COVERED"
+
+{
+    "type": "function",
+    "function": {
+        "name": "compute_payout",
+        "description": "Calculate net payable claim amount by deducting excess from claimed amount based on the claim coverage status.",
+        "parameters": {
+            "type": "object",
+            "properties": {
+                "claimed_amount": {"type": "number", "description": "Total claimed repair or loss amount in dollars."},
+                "excess_amount": {"type": "number", "description": "Policy deductible / excess amount in dollars."},
+                "status": {
+                    "type": "string",
+                    "enum": ["COVERED", "DENIED", "PARTIALLY_COVERED"],
+                    "description": "The coverage determination status."
+                }
+            },
+            "required": ["claimed_amount", "excess_amount", "status"]
+        }
+    }
+}
'''
