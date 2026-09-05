"""
week5/run_week5.py — Master runner for Week 5 deliverables.

Steps:
  1. Generate traces (runs all 40 questions through the RAG pipeline)
  2. Sample 20 traces with seed=42
  3. Replay one trace (seed=99) and write replay_evidence.md
  4. Open-code all 20 sampled traces → write to notes.md (auto-populated,
     with [OBSERVATION NEEDED] placeholders for the human to fill in)
  5. Write taxonomy.md template (to be completed after open-coding)

Usage:
    cd /path/to/SelfAiLearn
    source venv/bin/activate
    python3 week5/run_week5.py

Model note:
  Trace generation uses openai/gpt-oss-20b (fast, ~0.5s/call) to build the
  corpus. The production generation.py still uses openai/gpt-oss-120b for
  graded deliverables. Both models share the same system prompt and params.
"""

import os
import sys
import json
import random
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from retrieval import search
from generation import generate_answer, SYSTEM_PROMPT
from tracer import load_traces, get_trace_by_id, write_trace, TRACES_PATH
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Fast model for trace generation (0.5s/call vs ~4min for 120b)
# The production generation.py still uses 120b for real graded answers.
TRACE_MODEL = "openai/gpt-oss-20b"
TRACE_MODEL_PARAMS = {"temperature": 0.0, "max_tokens": 600}
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def generate_trace_answer(question: str, hits: list[dict], golden_id=None) -> dict:
    """
    Fast trace-generation variant: uses gpt-oss-20b instead of 120b.
    Writes a full trace to traces.jsonl via write_trace().
    """
    import os
    from generation import format_context
    client = OpenAI(
        api_key=os.environ.get("GROQ_API_KEY", ""),
        base_url=GROQ_BASE_URL,
        timeout=30.0,
    )
    context = format_context(hits)
    user_message = (
        f"CONTEXT FROM INDEXED ENDORSEMENTS:\n\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer using ONLY the context above. Cite each claim with "
        f"[SOURCE: chunk_id | form_number | clause_id]. "
        f"If the answer is not in the context, issue the REFUSAL message exactly."
    )
    response = client.chat.completions.create(
        model=TRACE_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        **TRACE_MODEL_PARAMS,
    )
    answer = response.choices[0].message.content.strip()
    is_refusal = answer.startswith("REFUSAL:")
    trace_id = write_trace(
        question=question,
        retrieved_chunks=hits,
        model=TRACE_MODEL,
        model_params=TRACE_MODEL_PARAMS,
        raw_output=answer,
        is_refusal=is_refusal,
        golden_id=golden_id,
    )
    return {"trace_id": trace_id, "answer": answer, "is_refusal": is_refusal}

WEEK5_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(WEEK5_DIR, "..")

SEED = 42
REPLAY_SEED = 99
SAMPLE_SIZE = 20

# ---------------------------------------------------------------------------
# Question bank (same as generate_traces.py)
# ---------------------------------------------------------------------------

QUESTION_BANK = [
    ("Does exclusion E-17 apply under form HO-0304 ed. 03-24, and is a burst supply line covered?", 1),
    ("What does sudden and accidental mean under CLAUSE WD-1 in HO-0304?", 2),
    ("What is a supply line as defined in HO-0304 CLAUSE WD-2?", 7),
    ("Under HO-0304 ed. 03-24, what is the maximum number of consecutive days of leakage before reclassification as gradual seepage?", None),
    ("Is continuous leakage from a pipe covered under HO-0304?", None),
    ("Does HO-0304 cover damage from a slowly dripping appliance hose?", None),
    ("What exclusions apply to water damage under HO-0304?", None),
    ("Does exclusion E-18 appear in HO-0304?", None),
    ("What is the Named Storm deductible amount under HO-0305 ed. 03-24?", 3),
    ("Does HO-0305 define what qualifies as a Named Storm event?", None),
    ("What triggers the Named Storm deductible under HO-0305?", None),
    ("Is the Named Storm deductible in HO-0305 a flat amount or a percentage?", None),
    ("Is mold damage covered under HO-0306 if it results from a sudden water discharge?", 5),
    ("Does HO-0306 cover air quality testing and mold sampling costs?", 6),
    ("Is there a sublimit for mold remediation under HO-0306?", None),
    ("What does HO-0306 say about fungi that grow on wood framing?", None),
    ("Does HO-0306 exclude mold that results from long-term humidity?", None),
    ("Under HO-0306, is the policyholder required to mitigate mold growth?", None),
    ("Under HO-0307, are scheduled jewelry items covered for mysterious disappearance?", 11),
    ("What property must be scheduled under HO-0307 to receive coverage?", None),
    ("Is there a per-item limit under HO-0307 for unscheduled items?", None),
    ("Does HO-0307 cover newly acquired jewelry for the first 30 days?", None),
    ("Does HO-0308 exclude sinkhole collapse damage? What exclusion code applies?", 8),
    ("Is earthquake damage excluded under HO-0308 ed. 05-24, including aftershocks?", 9),
    ("If earth movement and a covered peril cause loss together under HO-0308, what happens to coverage?", 12),
    ("Does HO-0308 apply the concurrent causation rule to earth movement losses?", None),
    ("Is volcanic eruption treated as earth movement under HO-0308?", None),
    ("What is exclusion E-32 in HO-0308?", None),
    ("Does HO-0308 exclude land subsidence?", None),
    ("Does exclusion E-19 appear in HO-0309 ed. 05-24 for business pursuits?", 4),
    ("Does HO-0309 cover liability from a home day care operation?", 10),
    ("Is freelance consulting work excluded under HO-0309?", None),
    ("Does HO-0309 cover business equipment stored at home?", None),
    ("What is exclusion E-36 in HO-0309?", None),
    ("Does HO-0309 exclude income-generating Airbnb activity?", None),
    ("What was the payout on the burst-pipe claim at the Riverside address last March?", None),
    ("Who is the assigned adjuster for claim CLM-2025-19234?", None),
    ("What is the reserve amount for the earth-movement claim filed last quarter?", None),
    ("What is the underwriting guideline for coastal flood zone AE maximum insured value?", None),
    ("Has subrogation been pursued on the supply-line claim from March 2024?", None),
    ("What does the base HO-3 wording say about mold that is not in the endorsement?", None),
    ("Is earthquake coverage available as an add-on under this insurer's commercial line?", None),
]


# ---------------------------------------------------------------------------
# Step 1 — Generate traces
# ---------------------------------------------------------------------------

def step1_generate_traces():
    existing = load_traces()
    print(f"\n[1/4] Trace generation")
    print(f"      Existing traces: {len(existing)}")

    if len(existing) >= SAMPLE_SIZE + 5:
        print(f"      ✅ Sufficient traces exist ({len(existing)}). Skipping generation.")
        return len(existing)

    print(f"      Running {len(QUESTION_BANK)} questions through RAG pipeline...")

    new_count = 0
    for i, (question, golden_id) in enumerate(QUESTION_BANK, 1):
        try:
            hits = search(question, strategy="structure_aware", n_results=5)
            result = generate_trace_answer(question=question, hits=hits, golden_id=golden_id)
            ref = " [REFUSAL]" if result["is_refusal"] else ""
            print(f"  [{i:02d}] {result['trace_id'][:12]}...{ref}  {question[:55]}...")
            new_count += 1
        except Exception as e:
            print(f"  [{i:02d}] ERROR: {e}")

    total = len(load_traces())
    print(f"      ✅ {new_count} new traces written. Total: {total}")
    return total


# ---------------------------------------------------------------------------
# Step 2 — Sample 20 traces
# ---------------------------------------------------------------------------

def step2_sample(traces: list[dict]) -> list[dict]:
    print(f"\n[2/4] Seeded random sample (seed={SEED})")
    rng = random.Random(SEED)
    sampled = rng.sample(traces, min(SAMPLE_SIZE, len(traces)))

    output = {
        "seed": SEED,
        "sample_size": len(sampled),
        "total_corpus": len(traces),
        "sampled_trace_ids": [t["trace_id"] for t in sampled],
    }
    out_path = os.path.join(WEEK5_DIR, "sampled_trace_ids.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"      ✅ {len(sampled)} traces sampled. IDs saved to week5/sampled_trace_ids.json")
    return sampled


# ---------------------------------------------------------------------------
# Step 3 — Replay one trace
# ---------------------------------------------------------------------------

def step3_replay(traces: list[dict]) -> dict:
    print(f"\n[3/4] Trace replay (seed={REPLAY_SEED})")
    from replay_trace import replay_trace, print_report

    rng = random.Random(REPLAY_SEED)
    chosen = rng.choice(traces)
    print(f"      Replaying trace: {chosen['trace_id']}")
    print(f"      (LLM call in progress...)")

    result = replay_trace(chosen)
    evidence_path = os.path.join(WEEK5_DIR, "replay_evidence.md")
    print_report(result, output_path=evidence_path)
    print(f"      ✅ Replay evidence written to week5/replay_evidence.md")
    return result


# ---------------------------------------------------------------------------
# Step 4 — Write notes.md and taxonomy.md templates
# ---------------------------------------------------------------------------

def step4_write_deliverables(sampled: list[dict], replay_result: dict, total_traces: int):
    print(f"\n[4/4] Writing deliverable templates")

    today = datetime.now().strftime("%Y-%m-%d")

    # ── notes.md ──────────────────────────────────────────────────────────────
    notes_path = os.path.join(WEEK5_DIR, "notes.md")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("# Week 5 — Notes (Open-Coding + Evidence)\n\n")
        f.write(f"**Date:** {today}  \n")
        f.write(f"**Domain:** Insurance Claims — Homeowners Endorsements  \n\n")

        # PII statement
        f.write("## PII Redaction Confirmation\n\n")
        f.write("> Claimant names and claim numbers are redacted **before** the trace "
                "is written to `traces.jsonl`, not after. The `redact()` function in "
                "`src/tracer.py` strips `CLM-YYYY-NNNNN` patterns and proper-name pairs "
                "from the question string at write time. No raw claimant identifier "
                "ever reaches disk.\n\n")

        # Seeded sample
        f.write("## Seeded Random Sample\n\n")
        f.write(f"- **Random seed:** `{SEED}`\n")
        f.write(f"- **Total traces in corpus:** {total_traces}\n")
        f.write(f"- **Sample size:** {len(sampled)}\n\n")
        f.write("| # | trace_id | refusal? | question (first 80 chars) |\n")
        f.write("|---|----------|----------|---------------------------|\n")
        for i, t in enumerate(sampled, 1):
            ref = "YES" if t.get("is_refusal") else "no"
            q = t.get("question", "")[:80].replace("|", "\\|")
            f.write(f"| {i} | `{t['trace_id']}` | {ref} | {q} |\n")

        # Replay evidence
        f.write("\n## Replay Evidence\n\n")
        f.write(f"**Trace replayed:** `{replay_result['trace_id']}`  \n")
        f.write(f"**Replay seed used:** `{REPLAY_SEED}`  \n")
        f.write(f"**Prompt version:** `{replay_result['prompt_version']}`  \n")
        f.write(f"**Model:** `{replay_result['model']}`  \n")
        f.write(f"**Model params:** `{replay_result['params']}`  \n")
        f.write(f"**Chunks retrieved:** {', '.join([f'`{c}`' for c in replay_result['chunks_used']])}  \n\n")
        f.write("### Required Field Audit\n\n")
        f.write("| Field | Present? |\n|-------|----------|\n")
        for field, info in replay_result["field_status"].items():
            icon = "✅" if info["present"] else "❌ MISSING"
            f.write(f"| `{field}` | {icon} |\n")
        f.write(f"\n> {replay_result['notes']}\n\n")
        f.write("### Original Output\n\n")
        f.write(f"```\n{replay_result['original_output']}\n```\n\n")
        f.write("### Replayed Output\n\n")
        f.write(f"```\n{replay_result['replayed_output']}\n```\n\n")

        # Open-coding sentences
        f.write("## Open-Coding — 20 Observation Sentences\n\n")
        f.write("> **Rule:** One honest sentence per trace describing what was SEEN. "
                "No category labels, no diagnoses, no fixes. "
                "'I don't know why this failed' is a permitted sentence.\n\n")
        f.write("> ⚠️  Zero code changes were made during this open-coding step.\n\n")
        for i, t in enumerate(sampled, 1):
            tid = t["trace_id"]
            q = t.get("question", "")
            raw = t.get("raw_output", "")
            is_ref = t.get("is_refusal", False)
            chunks = t.get("retrieved_chunks", [])
            forms_hit = list({c.get("form_number","?") for c in chunks})
            scores = [c.get("score", 0.0) for c in chunks]
            top_score = max(scores) if scores else 0.0

            # Auto-populate what's observable from the trace data
            f.write(f"### Trace {i:02d}: `{tid}`\n\n")
            f.write(f"**Question:** {q}  \n")
            f.write(f"**is_refusal:** {is_ref}  \n")
            f.write(f"**Top retrieval score:** {top_score:.4f}  \n")
            f.write(f"**Forms in top-5:** {', '.join(forms_hit)}  \n")
            f.write(f"**Output (first 300 chars):** `{raw[:300]}`  \n\n")
            f.write(f"**OBSERVATION:** [FILL IN — one sentence describing what you SAW]\n\n")
            f.write("---\n\n")

        # Dated prediction
        f.write("## Dated Prediction\n\n")
        f.write(f"**Date:** {today}  \n")
        f.write(f"**Failure mode targeted:** [FILL IN — the #1 mode from taxonomy.md]  \n")
        f.write(f"**Specific change:** [FILL IN — e.g. 'filter retrieval by edition_date']  \n")
        f.write(f"**Expected delta:** [FILL IN — e.g. 'drops from X% to under Y%']  \n\n")
        f.write(f"**Git commit hash:** [PASTE COMMIT HASH HERE after `git commit`]\n\n")

        # Benchmark note
        f.write("## Why Public Benchmarks Would Have Missed These Modes\n\n")
        f.write("[FILL IN — 3 sentences explaining why MMLU / HellaSwag / TruthfulQA "
                "would not surface your top-3 failure modes. "
                "Hint: your failures are about specific insurance form editions, "
                "exact exclusion codes, and citation provenance — not general knowledge.]\n\n")

    print(f"      ✅ notes.md template written to week5/notes.md")

    # ── taxonomy.md ───────────────────────────────────────────────────────────
    taxonomy_path = os.path.join(WEEK5_DIR, "taxonomy.md")
    with open(taxonomy_path, "w", encoding="utf-8") as f:
        f.write("# Week 5 — Failure Mode Taxonomy\n\n")
        f.write(f"**Date:** {today}  \n")
        f.write(f"**Sample:** {len(sampled)} randomly drawn traces (seed={SEED})  \n")
        f.write(f"**Corpus:** {total_traces} total traces  \n\n")
        f.write("> Modes named for a stranger: legible without knowing the codebase.\n\n")
        f.write("| Mode Name | Count | Freq % | Severity | Example trace_id |\n")
        f.write("|-----------|-------|--------|----------|------------------|\n")
        f.write("| [FILL IN after open-coding] | — | —% | wrongly denies / wrongly pays / annoys adjuster | `trace_id` |\n")
        f.write("| [FILL IN] | — | —% | — | `trace_id` |\n")
        f.write("| [FILL IN] | — | —% | — | `trace_id` |\n")
        f.write("| [FILL IN] | — | —% | — | `trace_id` |\n\n")
        f.write("> **Severity key:**  \n")
        f.write("> - `wrongly denies claim` — HIGH (bad-faith exposure)  \n")
        f.write("> - `wrongly pays claim` — HIGH (financial loss)  \n")
        f.write("> - `annoys adjuster` — LOW (friction, no coverage impact)  \n\n")
        f.write("## Notes\n\n")
        f.write("See `week5/notes.md` for all 20 verbatim open-coding sentences, "
                "the seeded sample list, and the replay evidence.\n")

    print(f"      ✅ taxonomy.md template written to week5/taxonomy.md")

    print(f"\n{'='*65}")
    print(f"  Week 5 runner complete!")
    print(f"{'='*65}")
    print(f"\n  NEXT STEPS (manual work — do NOT change any code):")
    print(f"  1. Open week5/notes.md")
    print(f"     → Read each of the 20 traces and fill in [OBSERVATION] sentences")
    print(f"  2. Open week5/taxonomy.md")
    print(f"     → Cluster your 20 sentences into 4-7 named failure modes")
    print(f"  3. Fill in the Dated Prediction section of notes.md")
    print(f"  4. Run: git add week5/ && git commit -m 'week5: dated prediction {today}'")
    print(f"  5. Paste the commit hash into notes.md")
    print(f"\n  FILES WRITTEN:")
    print(f"  • traces.jsonl             (all traces — {total_traces} entries)")
    print(f"  • week5/sampled_trace_ids.json")
    print(f"  • week5/replay_evidence.md")
    print(f"  • week5/notes.md           (fill in 20 observations + prediction)")
    print(f"  • week5/taxonomy.md        (fill in after open-coding)")
    print(f"{'='*65}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("  Week 5 — Error Analysis Runner")
    print("  Insurance Claims RAG — Homeowners Endorsements")
    print("=" * 65)

    # Step 1: Generate traces
    total = step1_generate_traces()
    traces = load_traces()

    # Step 2: Sample
    sampled = step2_sample(traces)

    # Step 3: Replay one trace (calls LLM)
    try:
        sys.path.insert(0, WEEK5_DIR)
        replay_result = step3_replay(traces)
    except Exception as e:
        print(f"      ⚠️  Replay failed: {e}")
        print(f"         (You can run week5/replay_trace.py manually)")
        replay_result = {
            "trace_id": "N/A", "prompt_version": "N/A", "model": "N/A",
            "params": {}, "chunks_used": [], "field_status": {},
            "original_output": "Replay failed — run week5/replay_trace.py manually",
            "replayed_output": "N/A", "notes": "Run replay_trace.py manually",
        }

    # Step 4: Write deliverable templates
    step4_write_deliverables(sampled, replay_result, total)


if __name__ == "__main__":
    main()
