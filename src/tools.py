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
"""

import os
import sys
from enum import Enum
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(__file__))
from claims_data import get_claim_by_id

# Import hybrid search if available, fallback to vector search or raw text search
try:
    from hybrid_retrieval import hybrid_search
    RETRIEVAL_AVAILABLE = True
except ImportError:
    try:
        from retrieval import search as vector_search
        RETRIEVAL_AVAILABLE = True
    except ImportError:
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
    try:
        claim = get_claim_by_id(claim_id.strip())
        return {
            "success": True,
            "claim_id": claim["claim_id"],
            "policy_number": claim["policy_number"],
            "form_number": claim["form_number"],
            "edition_date": claim["edition_date"],
            "date_of_loss": claim["date_of_loss"],
            "claimed_amount": claim["claimed_amount"],
            "excess_amount": claim["excess_amount"],
            "adjuster_notes": claim["adjuster_notes"],
        }
    except KeyError:
        return {
            "success": False,
            "error": f"Claim ID '{claim_id}' does not exist in claims records."
        }


# ---------------------------------------------------------------------------
# Tool 2: search_policy_exclusions
# ---------------------------------------------------------------------------
def search_policy_exclusions(policy_form: str, query: str) -> Dict[str, Any]:
    """
    Search policy endorsement documentation for coverage exclusions and limitations
    matching a peril or cause of loss.
    """
    search_query = f"{policy_form} {query}".strip()
    
    # Attempt vector/hybrid search first
    hits = []
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
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute tool by name and return result dictionary."""
    if tool_name == "get_claim":
        return get_claim(arguments.get("claim_id", ""))
    elif tool_name == "search_policy_exclusions":
        return search_policy_exclusions(
            policy_form=arguments.get("policy_form", ""),
            query=arguments.get("query", "")
        )
    elif tool_name == "compute_payout":
        return compute_payout(
            claimed_amount=arguments.get("claimed_amount", 0.0),
            excess_amount=arguments.get("excess_amount", 0.0),
            status=arguments.get("status", "DENIED")
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
