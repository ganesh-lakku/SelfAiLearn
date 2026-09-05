"""
tracer.py — Structured JSONL trace writer for the Insurance Claims RAG system.

Week 5 requirement: every LLM call must write a complete, replayable trace to
traces.jsonl with these required fields:
  - trace_id          unique UUID per call
  - timestamp         ISO-8601 UTC
  - prompt_version    constant tied to the system prompt version
  - question          the user question (PII-redacted before write)
  - retrieved_chunks  list of {chunk_id, score, form_number, clause_id, text_snippet}
  - model             model name string
  - model_params      {temperature, max_tokens}
  - raw_output        the full string returned by the LLM
  - is_refusal        True if response starts with "REFUSAL:"
  - golden_id         optional — the golden-set question id if this is an eval run

PII REDACTION NOTE:
  Claimant names and claim numbers are redacted BEFORE the trace is written,
  not after. The redact() helper below strips patterns like CLM-YYYY-NNNNN
  and proper-name patterns from the question string before it reaches the log.
  This satisfies the Week 5 requirement: "confirm redaction happens before write".
"""

import os
import re
import json
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Trace file location — project root
# ---------------------------------------------------------------------------

TRACES_PATH = os.path.join(os.path.dirname(__file__), "..", "traces.jsonl")

# ---------------------------------------------------------------------------
# Prompt version — bump this string whenever you edit the system prompt.
# Lets you know which prompt produced which trace when replaying.
# ---------------------------------------------------------------------------

PROMPT_VERSION = "v1.0.0-week5"

# ---------------------------------------------------------------------------
# PII redaction — runs on the question BEFORE writing to disk
# ---------------------------------------------------------------------------

# Claim number pattern: CLM-2024-88431 style
_CLAIM_RE = re.compile(r"\bCLM-\d{4}-\d+\b", re.IGNORECASE)

# Street address numbers (e.g. "512 Elm Street")
_ADDR_NUM_RE = re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Blvd)\b")

# Proper-name heuristic: two consecutive Title-Case words not in a known form-number pattern
_PROPER_NAME_RE = re.compile(r"\b(?!HO-\d|CLAUSE|SECTION|EXCLUSION)[A-Z][a-z]+ [A-Z][a-z]+\b")


def redact(text: str) -> str:
    """
    Redact PII from a string before it is written to disk.
    Patterns removed:
      - Claim numbers (CLM-YYYY-NNNNN)
      - Street address numbers
      - Proper name pairs (heuristic — two consecutive Title-Case words)
    Returns the redacted string.
    """
    text = _CLAIM_RE.sub("[CLAIM-REDACTED]", text)
    text = _ADDR_NUM_RE.sub("[ADDRESS-REDACTED]", text)
    # Only apply name-heuristic to strings that look like they contain claim data
    # (questions with "claimant", "adjuster", "payout" etc.) to avoid redacting
    # form names like "Named Storm Deductible".
    lowered = text.lower()
    if any(kw in lowered for kw in ("claimant", "adjuster", "payout", "reserve", "subrogation")):
        text = _PROPER_NAME_RE.sub("[NAME-REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Core write function
# ---------------------------------------------------------------------------

def write_trace(
    question: str,
    retrieved_chunks: list[dict],
    model: str,
    model_params: dict,
    raw_output: str,
    is_refusal: bool,
    golden_id: int | None = None,
    trace_id: str | None = None,
) -> str:
    """
    Write one complete, replayable trace to traces.jsonl.

    Args:
        question:          The user question — PII is redacted here before write.
        retrieved_chunks:  List of hit dicts from retrieval.search().
        model:             Model name string (e.g. "openai/gpt-oss-120b").
        model_params:      Dict of params sent to the API (temperature, max_tokens).
        raw_output:        The full raw string returned by the LLM.
        is_refusal:        True if raw_output starts with "REFUSAL:".
        golden_id:         The golden-set question id (for eval runs), or None.
        trace_id:          If provided, use this id (for deterministic testing).
                           Otherwise a fresh UUID4 is generated.

    Returns:
        The trace_id string (so callers can reference it).
    """
    tid = trace_id or str(uuid.uuid4())

    # PII redaction happens HERE — before ANY field is written to disk.
    safe_question = redact(question)

    # Serialise retrieved chunks — only the fields needed to replay the trace.
    chunk_records = []
    for h in retrieved_chunks:
        meta = h.get("metadata", {})
        chunk_records.append({
            "chunk_id":    h.get("chunk_id", ""),
            "rank":        h.get("rank", 0),
            "score":       h.get("score", 0.0),
            "form_number": meta.get("form_number", ""),
            "edition_date":meta.get("edition_date", ""),
            "clause_id":   meta.get("clause_id", ""),
            "text_snippet": h.get("text", "")[:300],   # first 300 chars — enough to replay
        })

    record = {
        "trace_id":         tid,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "prompt_version":   PROMPT_VERSION,
        "question":         safe_question,              # already redacted
        "retrieved_chunks": chunk_records,
        "model":            model,
        "model_params":     model_params,
        "raw_output":       raw_output,
        "is_refusal":       is_refusal,
        "golden_id":        golden_id,                  # None for non-eval calls
    }

    # Append to JSONL file — one JSON object per line.
    with open(TRACES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return tid


# ---------------------------------------------------------------------------
# Reader utilities
# ---------------------------------------------------------------------------

def load_traces(path: str | None = None) -> list[dict]:
    """Load all traces from the JSONL file and return as a list of dicts."""
    p = path or TRACES_PATH
    if not os.path.exists(p):
        return []
    traces = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    return traces


def get_trace_by_id(trace_id: str, path: str | None = None) -> dict | None:
    """Fetch a single trace by trace_id. Returns None if not found."""
    for t in load_traces(path):
        if t["trace_id"] == trace_id:
            return t
    return None


def count_traces(path: str | None = None) -> int:
    """Return the number of traces currently in the file."""
    return len(load_traces(path))
