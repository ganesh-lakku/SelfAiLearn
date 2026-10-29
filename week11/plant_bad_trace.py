#!/usr/bin/env python3
"""
week11/plant_bad_trace.py — Plant one bad coverage answer in traces.jsonl.

THE BUG: A claimant asks whether mold from HVAC condensation is covered under
HO-0306. The system answers "yes, covered under the remediation sublimit
exception (CLAUSE MF-2)" — but IGNORES exclusion E-27 which EXPLICITLY
excludes "Mold from HVAC condensation (chronic)" when the HVAC system was
not serviced in 3 years.

This is the exact scenario the Week 11 drill describes: "an adjuster says
it told a claimant something was covered when the policy excludes it."

The planted trace is timestamped "yesterday" (relative to now) to match
the vague complaint: "sometime yesterday".
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

TRACES_PATH = os.path.join(os.path.dirname(__file__), "..", "traces.jsonl")

# The bad answer — says mold from HVAC condensation IS covered,
# ignoring exclusion E-27 in HO-0306.
BAD_TRACE = {
    "trace_id": str(uuid.uuid4()),
    "timestamp": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
    "prompt_version": "v1.0.0-week5",
    "question": "Is mold from HVAC condensation covered under HO-0306?",
    "retrieved_chunks": [
        {
            "chunk_id": "HO-0306_sa_chunk_004",
            "rank": 1,
            "score": 0.6234,
            "form_number": "HO-0306",
            "edition_date": "04-24",
            "clause_id": "CLAUSE-MF-2",
            "text_snippet": "[HO-0306 ed. 04-24] CLAUSE-MF-2\nCLAUSE MF-2 — REMEDIATION SUBLIMIT EXCEPTION\nNotwithstanding CLAUSE MF-1, if mold is a direct result of a covered sudden\nand accidental water discharge event (as defined in form HO-0304 ed. 03-24,"
        },
        {
            "chunk_id": "HO-0306_sa_chunk_005",
            "rank": 2,
            "score": 0.5891,
            "form_number": "HO-0306",
            "edition_date": "04-24",
            "clause_id": "CLAUSE-WD-1",
            "text_snippet": "[HO-0306 ed. 04-24] CLAUSE-WD-1\nCLAUSE WD-1), we will pay up to $10,000 for mold remediation costs, provided:\n  (a) The water event is reported within 72 hours of discovery, and\n  (b) A licensed remediation contractor provides a written estimate."
        },
        {
            "chunk_id": "HO-0306_sa_chunk_003",
            "rank": 3,
            "score": 0.5622,
            "form_number": "HO-0306",
            "edition_date": "04-24",
            "clause_id": "CLAUSE-MF-1",
            "text_snippet": "[HO-0306 ed. 04-24] CLAUSE-MF-1\nCLAUSE MF-1 — MOLD AND FUNGI EXCLUSION (GENERAL)\nWe do not cover loss caused directly or indirectly by mold, fungi, wet rot,\ndry rot, or bacteria. This exclusion applies regardless of whether the mold\nor fungi results from a covered or uncovered water event."
        },
        {
            "chunk_id": "HO-0306_sa_chunk_001",
            "rank": 4,
            "score": 0.5200,
            "form_number": "HO-0306",
            "edition_date": "04-24",
            "clause_id": "PREAMBLE",
            "text_snippet": "[HO-0306 ed. 04-24] PREAMBLE\nForm Number: HO-0306\nEdition Date: 04-24\nPolicy Line: homeowners\nEffective Date: April 1, 2024\nTitle: Mold, Fungi, and Wet Rot Exclusion Endorsement"
        },
        {
            "chunk_id": "HO-0306_sa_chunk_002",
            "rank": 5,
            "score": 0.4980,
            "form_number": "HO-0306",
            "edition_date": "04-24",
            "clause_id": "SECTION-I",
            "text_snippet": "[HO-0306 ed. 04-24] SECTION-I\nSECTION I — PURPOSE\nThis endorsement clarifies and strengthens the policy's treatment of mold,\nfungi, wet rot, dry rot, and bacteria-related losses that may arise from\nor in connection with a covered water loss event."
        }
    ],
    "model": "openai/gpt-oss-120b",
    "model_params": {"temperature": 0.0, "max_tokens": 800},
    "raw_output": (
        "Yes, mold resulting from HVAC condensation can be covered under HO-0306. "
        "Under the remediation sublimit exception (CLAUSE MF-2), if mold is a direct "
        "result of a covered water discharge event, the endorsement will pay up to "
        "$10,000 for mold remediation costs, provided the water event is reported "
        "within 72 hours and a licensed contractor provides a written estimate. "
        "[SOURCE: HO-0306_sa_chunk_004 | HO-0306 | CLAUSE-MF-2] "
        "[SOURCE: HO-0306_sa_chunk_005 | HO-0306 | CLAUSE-WD-1]"
    ),
    "is_refusal": False,
    "golden_id": None,
}


def plant():
    """Append the bad trace to traces.jsonl."""
    with open(TRACES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(BAD_TRACE, ensure_ascii=False) + "\n")
    print(f"✅ Planted bad trace: {BAD_TRACE['trace_id']}")
    print(f"   Timestamp: {BAD_TRACE['timestamp']}")
    print(f"   Question:  {BAD_TRACE['question']}")
    print(f"   Bug:       Says HVAC mold is covered — ignores exclusion E-27")
    return BAD_TRACE["trace_id"]


if __name__ == "__main__":
    plant()
