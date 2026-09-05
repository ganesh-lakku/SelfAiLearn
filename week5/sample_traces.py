"""
week5/sample_traces.py — Draw a seeded random sample of 20 traces for Week 5.

Week 5 requirement:
  "Draw a RANDOM sample of 20 traces with a seeded selection you paste in
   the write-up. Not the demo claims, not the ones you remember breaking.
   Random, and provable."

This script:
  1. Loads all traces from traces.jsonl
  2. Uses random.seed(SEED) — paste SEED in notes.md
  3. Selects 20 random trace_ids (without replacement)
  4. Writes the sample list to week5/sampled_trace_ids.json
  5. Prints each selected trace summary for manual open-coding

Usage:
    cd /path/to/SelfAiLearn
    source venv/bin/activate
    python3 week5/sample_traces.py
"""

import os
import sys
import json
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tracer import load_traces

# ---------------------------------------------------------------------------
# Seed — PASTE THIS INTO notes.md
# ---------------------------------------------------------------------------
SEED = 42          # Week 5 documented seed — do not change after sampling
SAMPLE_SIZE = 20

TRACES_PATH = os.path.join(os.path.dirname(__file__), "..", "traces.jsonl")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "sampled_trace_ids.json")


def main():
    traces = load_traces()
    total = len(traces)

    if total == 0:
        print("❌ No traces found. Run week5/generate_traces.py first.")
        sys.exit(1)

    if total < SAMPLE_SIZE:
        print(f"⚠️  Only {total} traces available (need {SAMPLE_SIZE}).")
        print("   Run week5/generate_traces.py to generate more traces.")
        sys.exit(1)

    print(f"Total traces available: {total}")
    print(f"Random seed:            {SEED}  (paste this in notes.md)")
    print(f"Sample size:            {SAMPLE_SIZE}")
    print()

    # Seeded random selection
    rng = random.Random(SEED)
    sampled = rng.sample(traces, SAMPLE_SIZE)
    sampled_ids = [t["trace_id"] for t in sampled]

    # Save sampled list
    output = {
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "total_corpus": total,
        "sampled_trace_ids": sampled_ids,
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"{'─'*70}")
    print(f"{'#':>3}  {'trace_id':>38}  {'refusal':>8}  question (first 60 chars)")
    print(f"{'─'*70}")

    for i, trace in enumerate(sampled, 1):
        tid = trace["trace_id"]
        refusal = "YES" if trace.get("is_refusal") else "no"
        q = trace.get("question", "")[:60]
        print(f"{i:>3}  {tid:>38}  {refusal:>8}  {q}")

    print(f"{'─'*70}")
    print(f"\n✅ Sampled {SAMPLE_SIZE} traces written to: {OUTPUT_PATH}")
    print(f"\n   Next step: open each trace and write ONE observation sentence.")
    print(f"   Use: python3 week5/replay_trace.py <trace_id> to inspect any trace.")
    print(f"\n   Paste into notes.md:")
    print(f"     Seed: {SEED}")
    print(f"     Sampled IDs:")
    for i, tid in enumerate(sampled_ids, 1):
        print(f"       {i:>2}. {tid}")


if __name__ == "__main__":
    main()
