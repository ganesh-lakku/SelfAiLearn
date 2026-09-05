"""
week5/generate_traces.py — Populate traces.jsonl with enough traces to sample from.

This script runs ALL golden-set questions through the RAG pipeline multiple times
with slight question variations to build a realistic trace corpus of 50+ traces.
Then Week 5's sample_traces.py draws 20 random ones from this corpus.

It does NOT fix or change anything in the system. It only exercises what
the system already does, across the full question space.

Usage:
    cd /path/to/SelfAiLearn
    source venv/bin/activate
    python3 week5/generate_traces.py
"""

import os
import sys
import json

# Make src/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from retrieval import search
from generation import generate_answer
from tracer import load_traces, TRACES_PATH

# ---------------------------------------------------------------------------
# Extended question set — covers all 6 forms, multiple question types
# Each tuple: (question_text, golden_id_or_None)
# golden_id ties this to the golden_set.jsonl question if applicable.
# ---------------------------------------------------------------------------

QUESTION_BANK = [
    # ── HO-0304 Water damage / supply line ───────────────────────────────────
    ("Does exclusion E-17 apply under form HO-0304 ed. 03-24, and is a burst supply line covered?", 1),
    ("What does sudden and accidental mean under CLAUSE WD-1 in HO-0304?", 2),
    ("What is a supply line as defined in HO-0304 CLAUSE WD-2?", 7),
    ("Under HO-0304 ed. 03-24, what is the maximum number of consecutive days of leakage before reclassification as gradual seepage?", None),
    ("Is continuous leakage from a pipe covered under HO-0304?", None),
    ("Does HO-0304 cover damage from a slowly dripping appliance hose?", None),
    ("What exclusions apply to water damage under HO-0304?", None),
    ("Does exclusion E-18 appear in HO-0304?", None),

    # ── HO-0305 Named storm deductible ───────────────────────────────────────
    ("What is the Named Storm deductible amount under HO-0305 ed. 03-24?", 3),
    ("Does HO-0305 define what qualifies as a Named Storm event?", None),
    ("What triggers the Named Storm deductible under HO-0305?", None),
    ("Is the Named Storm deductible in HO-0305 a flat amount or a percentage?", None),

    # ── HO-0306 Mold / fungi ─────────────────────────────────────────────────
    ("Is mold damage covered under HO-0306 if it results from a sudden water discharge?", 5),
    ("Does HO-0306 cover air quality testing and mold sampling costs?", 6),
    ("Is there a sublimit for mold remediation under HO-0306?", None),
    ("What does HO-0306 say about fungi that grow on wood framing?", None),
    ("Does HO-0306 exclude mold that results from long-term humidity?", None),
    ("Under HO-0306, is the policyholder required to mitigate mold growth?", None),

    # ── HO-0307 Scheduled personal property ──────────────────────────────────
    ("Under HO-0307, are scheduled jewelry items covered for mysterious disappearance?", 11),
    ("What property must be scheduled under HO-0307 to receive coverage?", None),
    ("Is there a per-item limit under HO-0307 for unscheduled items?", None),
    ("Does HO-0307 cover newly acquired jewelry for the first 30 days?", None),

    # ── HO-0308 Earth movement ────────────────────────────────────────────────
    ("Does HO-0308 exclude sinkhole collapse damage? What exclusion code applies?", 8),
    ("Is earthquake damage excluded under HO-0308 ed. 05-24, including aftershocks?", 9),
    ("If earth movement and a covered peril cause loss together under HO-0308, what happens to coverage?", 12),
    ("Does HO-0308 apply the concurrent causation rule to earth movement losses?", None),
    ("Is volcanic eruption treated as earth movement under HO-0308?", None),
    ("What is exclusion E-32 in HO-0308?", None),
    ("Does HO-0308 exclude land subsidence?", None),

    # ── HO-0309 Business pursuits ────────────────────────────────────────────
    ("Does exclusion E-19 appear in HO-0309 ed. 05-24 for business pursuits?", 4),
    ("Does HO-0309 cover liability from a home day care operation?", 10),
    ("Is freelance consulting work excluded under HO-0309?", None),
    ("Does HO-0309 cover business equipment stored at home?", None),
    ("What is exclusion E-36 in HO-0309?", None),
    ("Does HO-0309 exclude income-generating Airbnb activity?", None),

    # ── Out-of-corpus / refusal probes ───────────────────────────────────────
    ("What was the payout on the burst-pipe claim at the Riverside address last March?", None),
    ("Who is the assigned adjuster for claim CLM-2025-19234?", None),
    ("What is the reserve amount for the earth-movement claim filed last quarter?", None),
    ("What is the underwriting guideline for coastal flood zone AE maximum insured value?", None),
    ("Has subrogation been pursued on the supply-line claim from March 2024?", None),
    ("What does the base HO-3 wording say about mold that is not in the endorsement?", None),
    ("Is earthquake coverage available as an add-on under this insurer's commercial line?", None),
]


def main():
    # Check if we already have enough traces
    existing = load_traces()
    print(f"Existing traces in {TRACES_PATH}: {len(existing)}")

    if len(existing) >= 50:
        print("✅ Already have 50+ traces. Ready for Week 5 sampling.")
        print("   Run: python3 week5/sample_traces.py")
        return

    print(f"\nRunning {len(QUESTION_BANK)} questions through the RAG pipeline...")
    print("Each call writes one trace to traces.jsonl.\n")

    for i, (question, golden_id) in enumerate(QUESTION_BANK, 1):
        print(f"[{i:02d}/{len(QUESTION_BANK)}] {question[:80]}{'...' if len(question) > 80 else ''}")
        try:
            hits = search(question, strategy="structure_aware", n_results=5)
            result = generate_answer(
                question=question,
                hits=hits,
                verbose=False,
                golden_id=golden_id,
            )
            refusal_tag = "  [REFUSAL]" if result["is_refusal"] else ""
            print(f"         trace_id={result['trace_id'][:8]}...{refusal_tag}")
        except Exception as e:
            print(f"         ERROR: {e}")

    final_count = len(load_traces())
    print(f"\n✅ Done. Total traces now: {final_count}")
    print(f"   Trace file: {TRACES_PATH}")
    print(f"\n   Next step: python3 week5/sample_traces.py")


if __name__ == "__main__":
    main()
