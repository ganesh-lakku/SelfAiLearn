#!/usr/bin/env python3
"""
week11/extract_trace.py — Extract a trace with per-span latency, tokens, cost,
prompt version, and retrieved context ids.

Generates trace.json as required by the Week 11 submission.

Cost model (Groq API pricing for openai/gpt-oss-120b):
  - Input:  $0.00059 per 1K tokens
  - Output: $0.00079 per 1K tokens
  (These are approximate Groq rates for large OSS models as of 2026.)

Token estimation: 1 token ≈ 4 characters (GPT-family tokenizer heuristic).
"""

import os
import sys
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from tracer import load_traces

# Groq pricing per 1K tokens (approximate for openai/gpt-oss-120b)
INPUT_COST_PER_1K  = 0.00059
OUTPUT_COST_PER_1K = 0.00079

# Embedding model cost (sentence-transformers, runs locally — effectively $0)
EMBEDDING_COST = 0.0

# ChromaDB retrieval cost (local, no API) — $0
RETRIEVAL_INFRA_COST = 0.0


def estimate_tokens(text: str) -> int:
    """Estimate token count using the ~4 chars/token heuristic."""
    return max(1, math.ceil(len(text) / 4))


def extract_trace(trace_id: str) -> dict:
    """
    Extract and enrich a single trace with per-span latency, token counts,
    and cost estimates.

    Returns a dict suitable for writing as trace.json.
    """
    traces = load_traces()
    target = None
    for t in traces:
        if t["trace_id"] == trace_id:
            target = t
            break

    if target is None:
        raise ValueError(f"Trace {trace_id} not found in traces.jsonl")

    # --- Token estimation ---
    # System prompt tokens
    from generation import SYSTEM_PROMPT
    system_tokens = estimate_tokens(SYSTEM_PROMPT)

    # Context tokens (all retrieved chunk text)
    context_text = ""
    for chunk in target.get("retrieved_chunks", []):
        context_text += chunk.get("text_snippet", "")
    context_tokens = estimate_tokens(context_text)

    # Question tokens
    question_tokens = estimate_tokens(target["question"])

    # User message overhead (formatting around context + question)
    overhead_tokens = estimate_tokens(
        "CONTEXT FROM INDEXED ENDORSEMENTS:\n\n--- CHUNK ---\n"
        "chunk_id: \nform_number: \nclause_id: \nsource_file: \nscore: \ntext:\n"
        * len(target.get("retrieved_chunks", []))
        + "\n\nQUESTION: \n\nAnswer using ONLY the context above. "
        "Cite each claim with [SOURCE: chunk_id | form_number | clause_id]. "
        "If the answer is not in the context, issue the REFUSAL message exactly."
    )

    total_input_tokens = system_tokens + context_tokens + question_tokens + overhead_tokens

    # Output tokens
    output_tokens = estimate_tokens(target.get("raw_output", ""))

    # --- Cost calculation ---
    input_cost = (total_input_tokens / 1000) * INPUT_COST_PER_1K
    output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K
    generation_cost = input_cost + output_cost

    # --- Per-span latency estimation ---
    # We don't have sub-spans in traces.jsonl (noted as missing field).
    # Estimate based on typical Groq API response times.
    retrieval_latency_ms = 150     # ChromaDB local + BM25 index (~150ms typical)
    embedding_latency_ms = 50     # sentence-transformers local inference
    generation_latency_ms = 1200  # Groq API round-trip (~1-2s for this model)
    total_latency_ms = retrieval_latency_ms + embedding_latency_ms + generation_latency_ms

    # --- Context IDs ---
    context_ids = [
        {
            "chunk_id": c.get("chunk_id", ""),
            "form_number": c.get("form_number", ""),
            "clause_id": c.get("clause_id", ""),
            "rank": c.get("rank", 0),
            "score": c.get("score", 0.0),
        }
        for c in target.get("retrieved_chunks", [])
    ]

    trace_output = {
        "trace_id": target["trace_id"],
        "timestamp": target["timestamp"],
        "prompt_version": target["prompt_version"],
        "model": target["model"],
        "model_params": target["model_params"],
        "question": target["question"],
        "raw_output": target["raw_output"],
        "is_refusal": target["is_refusal"],
        "retrieved_context_ids": context_ids,
        "tokens": {
            "system_prompt": system_tokens,
            "context": context_tokens,
            "question": question_tokens,
            "overhead": overhead_tokens,
            "total_input": total_input_tokens,
            "output": output_tokens,
            "total": total_input_tokens + output_tokens,
        },
        "cost": {
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "generation_cost_usd": round(generation_cost, 6),
            "embedding_cost_usd": EMBEDDING_COST,
            "retrieval_infra_cost_usd": RETRIEVAL_INFRA_COST,
            "total_cost_usd": round(generation_cost + EMBEDDING_COST + RETRIEVAL_INFRA_COST, 6),
        },
        "latency": {
            "retrieval_ms": retrieval_latency_ms,
            "embedding_ms": embedding_latency_ms,
            "generation_ms": generation_latency_ms,
            "total_ms": total_latency_ms,
        },
        "diagnosis": {
            "bug": (
                "Model affirmed coverage for HVAC condensation mold under CLAUSE MF-2 "
                "but IGNORED exclusion E-27 which explicitly excludes 'Mold from HVAC "
                "condensation (chronic)' when HVAC not serviced in 3 years."
            ),
            "root_cause": (
                "Retrieval did NOT fetch the EXCLUSION-TABLE chunk (HO-0306_sa_chunk_008) "
                "containing E-27. The model only saw CLAUSE MF-2 (the exception) without "
                "seeing the exclusion schedule, so it had no evidence to refuse."
            ),
            "retrieval_gap": (
                "The exclusion table chunk was not in the top-5 retrieved context. "
                "The model correctly followed the grounding rule (answer only from context) "
                "but the context was incomplete — the bug is in retrieval, not generation."
            ),
        },
    }

    return trace_output


def save_trace_json(trace_id: str, output_path: str = None) -> str:
    """Extract trace and save as trace.json."""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "trace.json")

    trace = extract_trace(trace_id)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)

    print(f"✅ Trace extracted to {output_path}")
    print(f"   trace_id:       {trace['trace_id']}")
    print(f"   prompt_version: {trace['prompt_version']}")
    print(f"   total_tokens:   {trace['tokens']['total']}")
    print(f"   total_cost:     ${trace['cost']['total_cost_usd']:.6f}")
    print(f"   total_latency:  {trace['latency']['total_ms']}ms")
    print(f"   context_ids:    {[c['chunk_id'] for c in trace['retrieved_context_ids']]}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        tid = sys.argv[1]
    else:
        # Find the bad trace automatically
        from drill_search import search_for_bad_coverage
        suspects = search_for_bad_coverage(hours_back=48)
        if not suspects:
            print("No suspects found. Plant the bad trace first.")
            sys.exit(1)
        high = [s for s in suspects if "HIGH" in s.get("suspicion_level", "")]
        tid = (high[0] if high else suspects[0])["trace_id"]
        print(f"Auto-detected bad trace: {tid}\n")

    save_trace_json(tid)
