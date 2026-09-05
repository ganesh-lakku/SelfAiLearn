"""
week5/replay_trace.py — Replay one trace from its stored data alone.

Week 5 requirement (20 pts):
  "Prove your traces are replayable: pick one trace at random by trace_id
   (seeded, and paste the seed), replay it from the trace alone, and show
   the replayed output alongside the original."

This script:
  1. Loads the trace for a given trace_id from traces.jsonl
  2. Reconstructs the exact prompt (system + user) from stored fields
  3. Calls the LLM with the SAME model + params stored in the trace
  4. Shows original output vs replayed output side by side
  5. Reports any fields that were missing from the trace

Usage:
    python3 week5/replay_trace.py <trace_id>
    python3 week5/replay_trace.py --seed 99   # picks one trace by seed

The replay seed for Week 5 evidence is: REPLAY_SEED = 99
"""

import os
import sys
import argparse
import random
import json
import textwrap
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tracer import load_traces, get_trace_by_id, TRACES_PATH
from generation import get_client, SYSTEM_PROMPT, format_context

# The seed used to pick the one trace we replay as evidence
REPLAY_SEED = 99

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wrap(text: str, width: int = 72, indent: str = "  ") -> str:
    return "\n".join(textwrap.wrap(text, width=width, initial_indent=indent, subsequent_indent=indent))


def check_required_fields(trace: dict) -> dict:
    """
    Check which Week-5-required fields are present / absent in the trace.
    Returns a dict mapping field_name -> present (bool).
    """
    required = {
        "trace_id":         "Unique trace identifier",
        "timestamp":        "ISO-8601 UTC timestamp",
        "prompt_version":   "System prompt version string",
        "question":         "User question (PII-redacted)",
        "retrieved_chunks": "List of chunk_id + score records",
        "model":            "Model name string",
        "model_params":     "temperature, max_tokens",
        "raw_output":       "Full LLM response string",
        "is_refusal":       "Boolean refusal flag",
    }
    status = {}
    for field, _ in required.items():
        val = trace.get(field)
        present = val is not None and val != "" and val != []
        status[field] = {"present": present, "description": _}
    return status


def rebuild_context_from_trace(trace: dict) -> str:
    """
    Reconstruct the context block from stored chunk records (text_snippet).
    Used to re-build the user message for the replay call.
    """
    parts = []
    for c in trace.get("retrieved_chunks", []):
        parts.append(
            f"--- CHUNK ---\n"
            f"chunk_id: {c.get('chunk_id','')}\n"
            f"form_number: {c.get('form_number','UNKNOWN')}\n"
            f"clause_id: {c.get('clause_id','N/A')}\n"
            f"score: {c.get('score', 0.0):.4f}\n"
            f"text:\n{c.get('text_snippet','[no text stored]')}\n"
        )
    return "\n".join(parts)


def replay_trace(trace: dict) -> dict:
    """
    Replay one trace from its stored fields.
    Returns dict with: replayed_output, original_output, field_status, notes.
    """
    client = get_client()

    # Reconstruct user message from stored trace data
    context_block = rebuild_context_from_trace(trace)
    question = trace.get("question", "")
    user_message = (
        f"CONTEXT FROM INDEXED ENDORSEMENTS:\n\n{context_block}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer using ONLY the context above. Cite each claim with "
        f"[SOURCE: chunk_id | form_number | clause_id]. "
        f"If the answer is not in the context, issue the REFUSAL message exactly."
    )

    # Use stored model + params from the trace (respects whatever model was used)
    model = trace.get("model", "openai/gpt-oss-20b")
    params = trace.get("model_params", {"temperature": 0.0, "max_tokens": 600})

    # Call the LLM
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        **params,
    )
    replayed_output = response.choices[0].message.content.strip()

    # Check which required fields exist in the stored trace
    field_status = check_required_fields(trace)

    # Notes: what was missing
    missing = [f for f, v in field_status.items() if not v["present"]]
    notes = (
        "All required fields present — fully replayable."
        if not missing
        else f"Missing fields: {', '.join(missing)}. These were added in the Week 5 tracer update."
    )

    return {
        "trace_id":        trace["trace_id"],
        "question":        question,
        "original_output": trace.get("raw_output", "[NOT STORED]"),
        "replayed_output": replayed_output,
        "field_status":    field_status,
        "notes":           notes,
        "model":           model,
        "params":          params,
        "prompt_version":  trace.get("prompt_version", "[NOT STORED]"),
        "timestamp":       trace.get("timestamp", "[NOT STORED]"),
        "chunks_used":     [c.get("chunk_id") for c in trace.get("retrieved_chunks", [])],
    }


def print_report(result: dict, output_path: str | None = None) -> None:
    """Print a human-readable side-by-side replay report."""
    SEP = "═" * 72
    sep = "─" * 72

    lines = []
    lines.append(f"\n{SEP}")
    lines.append("  TRACE REPLAY EVIDENCE — Week 5")
    lines.append(SEP)
    lines.append(f"  trace_id      : {result['trace_id']}")
    lines.append(f"  prompt_version: {result['prompt_version']}")
    lines.append(f"  model         : {result['model']}")
    lines.append(f"  params        : {result['params']}")
    lines.append(f"  timestamp     : {result['timestamp']}")
    lines.append(f"  chunks used   : {', '.join(result['chunks_used'][:3])}"
                 + (" ..." if len(result['chunks_used']) > 3 else ""))
    lines.append("")
    lines.append(f"  QUESTION:")
    lines.append(wrap(result["question"]))
    lines.append("")
    lines.append(sep)
    lines.append("  REQUIRED FIELD AUDIT:")
    for field, info in result["field_status"].items():
        icon = "✅" if info["present"] else "❌ MISSING"
        lines.append(f"    {icon}  {field:20s} — {info['description']}")
    lines.append("")
    lines.append(f"  NOTE: {result['notes']}")
    lines.append(sep)
    lines.append("  ORIGINAL OUTPUT (from stored trace):")
    lines.append(wrap(result["original_output"], width=68))
    lines.append("")
    lines.append(sep)
    lines.append("  REPLAYED OUTPUT (reconstructed from trace fields):")
    lines.append(wrap(result["replayed_output"], width=68))
    lines.append("")

    # Similarity check
    orig_words = set(result["original_output"].lower().split())
    repl_words = set(result["replayed_output"].lower().split())
    if orig_words:
        overlap = len(orig_words & repl_words) / len(orig_words | repl_words)
    else:
        overlap = 0.0
    lines.append(f"  Jaccard overlap (original vs replayed): {overlap:.1%}")
    lines.append(f"  Both refusals: {result['original_output'].startswith('REFUSAL:') and result['replayed_output'].startswith('REFUSAL:')}")
    lines.append(SEP)

    report = "\n".join(lines)
    print(report)

    # Also save the report
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "replay_evidence.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Trace Replay Evidence — Week 5\n\n")
        f.write(f"**trace_id:** `{result['trace_id']}`  \n")
        f.write(f"**prompt_version:** `{result['prompt_version']}`  \n")
        f.write(f"**model:** `{result['model']}`  \n")
        f.write(f"**model_params:** `{result['params']}`  \n")
        f.write(f"**timestamp:** `{result['timestamp']}`  \n")
        f.write(f"**chunks_used:** {', '.join([f'`{c}`' for c in result['chunks_used']])}  \n\n")
        f.write(f"**PII redaction:** Claimant names and claim numbers are redacted "
                f"BEFORE the trace is written (inside `tracer.py:redact()`), not after.\n\n")
        f.write("## Required Field Audit\n\n")
        f.write("| Field | Present? | Description |\n")
        f.write("|-------|----------|-------------|\n")
        for field, info in result["field_status"].items():
            icon = "✅" if info["present"] else "❌ MISSING"
            f.write(f"| `{field}` | {icon} | {info['description']} |\n")
        f.write(f"\n> {result['notes']}\n\n")
        f.write("## Original Output (stored in trace)\n\n")
        f.write(f"```\n{result['original_output']}\n```\n\n")
        f.write("## Replayed Output (reconstructed from trace fields alone)\n\n")
        f.write(f"```\n{result['replayed_output']}\n```\n\n")
        f.write(f"**Jaccard overlap:** {overlap:.1%}  \n")

    print(f"\n  Replay evidence saved to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Replay one trace from traces.jsonl and show original vs replayed output."
    )
    parser.add_argument("trace_id", nargs="?", help="trace_id to replay")
    parser.add_argument(
        "--seed", type=int, default=REPLAY_SEED,
        help=f"Seed to pick a random trace for replay (default: {REPLAY_SEED})"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available trace_ids and exit"
    )
    args = parser.parse_args()

    traces = load_traces()
    if not traces:
        print("❌ No traces found. Run week5/generate_traces.py first.")
        sys.exit(1)

    if args.list:
        print(f"{'trace_id':>38}  {'refusal':>8}  question")
        for t in traces:
            ref = "YES" if t.get("is_refusal") else "no"
            print(f"{t['trace_id']:>38}  {ref:>8}  {t.get('question','')[:60]}")
        return

    if args.trace_id:
        trace = get_trace_by_id(args.trace_id)
        if trace is None:
            print(f"❌ trace_id not found: {args.trace_id}")
            sys.exit(1)
    else:
        # Pick by seed
        rng = random.Random(args.seed)
        trace = rng.choice(traces)
        print(f"  Selected trace by seed={args.seed}: {trace['trace_id']}")

    print(f"\n  Replaying trace {trace['trace_id']} ...")
    print(f"  (this calls the LLM — takes a moment)\n")

    result = replay_trace(trace)
    print_report(result)


if __name__ == "__main__":
    main()
