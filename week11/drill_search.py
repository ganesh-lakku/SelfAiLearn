#!/usr/bin/env python3
"""
week11/drill_search.py — Find the bad coverage answer in traces.jsonl.

The complaint: "an adjuster says it told a claimant something was covered
when the policy excludes it, sometime yesterday."

Strategy: scan traces for non-refusal answers that contain coverage-affirming
language ("covered", "pays", "will pay") AND overlap with known exclusion
domains, AND were generated "yesterday" (within the last 48h).

This is a SLICE-BASED search:
  - Slice 1: TIME     — filter to last 48h
  - Slice 2: OUTPUT   — search raw_output for coverage-affirming language
  - Slice 3: CONTEXT  — cross-check retrieved chunks for exclusion-table presence
"""

import os
import sys
import json
import re
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tracer import load_traces

# Coverage-affirming phrases — the complaint says "told a claimant something was covered"
_COVERAGE_AFFIRM_RE = re.compile(
    r"\b(is covered|can be covered|covered under|will pay|coverage applies|"
    r"the endorsement will pay|pays up to|remediation.*covered)\b",
    re.IGNORECASE,
)

# Known exclusion codes from all 6 endorsements
_EXCLUSION_RE = re.compile(r"\bE-\d{1,3}\b")

# Exclusion keywords that indicate the answer SHOULD have mentioned an exclusion
_EXCLUSION_DOMAINS = [
    "mold", "fungi", "seepage", "flood", "sewer", "ground water",
    "ice dam", "appliance wear", "intentional", "earth movement",
    "sinkhole", "volcanic", "business pursuits", "day care",
    "HVAC condensation", "bacteria", "wet rot", "dry rot",
]


def search_for_bad_coverage(hours_back: int = 48) -> list[dict]:
    """
    Search traces for coverage answers that may have ignored an exclusion.

    Returns list of suspect trace dicts with added 'suspicion_reason' field.
    """
    traces = load_traces()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    suspects = []

    for t in traces:
        # SLICE 1: TIME — only "yesterday" (within hours_back)
        ts = datetime.fromisoformat(t["timestamp"])
        if ts < cutoff:
            continue

        # Skip refusals — we're looking for WRONG coverage answers
        if t.get("is_refusal", False):
            continue

        raw = t.get("raw_output", "")

        # SLICE 2: OUTPUT — contains coverage-affirming language
        if not _COVERAGE_AFFIRM_RE.search(raw):
            continue

        # SLICE 3: CONTEXT — check if the question touches an exclusion domain
        question = t.get("question", "").lower()
        output_lower = raw.lower()

        # Check if the question or output mentions an exclusion domain
        domain_hit = None
        for domain in _EXCLUSION_DOMAINS:
            if domain.lower() in question or domain.lower() in output_lower:
                domain_hit = domain
                break

        if not domain_hit:
            continue

        # Check if the answer FAILS to mention the relevant exclusion code
        # A correct answer about an excluded peril should cite the exclusion
        retrieved_chunk_ids = [
            c.get("clause_id", "") for c in t.get("retrieved_chunks", [])
        ]
        has_exclusion_table = any("EXCLUSION" in cid for cid in retrieved_chunk_ids)

        # If the answer says "covered" and touches an exclusion domain
        # but does NOT mention any E-XX exclusion code → SUSPECT
        exclusion_codes_in_output = _EXCLUSION_RE.findall(raw)

        # High suspicion: affirms coverage in an exclusion domain without citing E-XX
        suspicion = "HIGH" if not exclusion_codes_in_output else "LOW"

        # Extra check: did retrieval even fetch the exclusion table?
        if not has_exclusion_table:
            suspicion = "HIGH — exclusion table NOT in retrieved context"

        t["suspicion_reason"] = (
            f"Affirms coverage in '{domain_hit}' domain. "
            f"Exclusion codes in output: {exclusion_codes_in_output or 'NONE'}. "
            f"Exclusion table retrieved: {has_exclusion_table}. "
            f"Suspicion: {suspicion}"
        )
        t["suspicion_level"] = suspicion
        suspects.append(t)

    return suspects


def run_drill() -> dict:
    """
    Run the full drill: search, time it, and report.
    Returns drill results dict.
    """
    print("=" * 64)
    print("  WEEK 11 DRILL — Finding the bad coverage answer")
    print("=" * 64)
    print()
    print("Complaint: 'an adjuster says it told a claimant something was")
    print("covered when the policy excludes it, sometime yesterday.'")
    print()

    start = time.time()

    # Run the search
    suspects = search_for_bad_coverage(hours_back=48)

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"⏱  Search completed in {minutes:02d}:{seconds:02d}")
    print(f"   Suspects found: {len(suspects)}")
    print()

    if not suspects:
        print("❌ No suspects found. Check if the bad trace was planted.")
        return {"found": False, "time_mm_ss": f"{minutes:02d}:{seconds:02d}"}

    # Rank by suspicion level
    high_suspects = [s for s in suspects if "HIGH" in s.get("suspicion_level", "")]
    low_suspects = [s for s in suspects if "LOW" in s.get("suspicion_level", "")]

    found_trace = None

    for i, s in enumerate(high_suspects + low_suspects):
        level = "🔴 HIGH" if s in high_suspects else "🟡 LOW"
        print(f"  Suspect #{i+1} [{level}]")
        print(f"    trace_id:  {s['trace_id']}")
        print(f"    timestamp: {s['timestamp']}")
        print(f"    question:  {s['question']}")
        print(f"    reason:    {s['suspicion_reason']}")
        print(f"    answer:    {s['raw_output'][:120]}...")
        print()
        if found_trace is None:
            found_trace = s

    # The slice that found it
    slice_used = "TIME (last 48h) + OUTPUT (coverage-affirming language) + CONTEXT (exclusion domain match without E-XX code)"

    result = {
        "found": True,
        "time_mm_ss": f"{minutes:02d}:{seconds:02d}",
        "slice_used": slice_used,
        "trace_id": found_trace["trace_id"],
        "timestamp": found_trace["timestamp"],
        "question": found_trace["question"],
        "suspicion_reason": found_trace["suspicion_reason"],
        "total_suspects": len(suspects),
        "high_suspects": len(high_suspects),
    }

    print(f"{'=' * 64}")
    print(f"  RESULT: Found in {minutes:02d}:{seconds:02d}")
    print(f"  Slice:  {slice_used}")
    print(f"  Trace:  {found_trace['trace_id']}")
    print(f"{'=' * 64}")

    return result


if __name__ == "__main__":
    run_drill()
