"""
week6/summariser.py — Claim summary generator for Week 6 eval.

Takes adjuster notes + claim metadata and produces a structured claim summary.
This is the output that the LLM judge will evaluate.

The summary prompt is deliberately simple — it should produce real-world-quality
summaries that sometimes contain invented coverage (which the judge must catch).
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
SUMMARY_MODEL = "openai/gpt-oss-120b"
SUMMARY_MODEL_PARAMS = {"temperature": 0.0, "max_tokens": 500}

SUMMARIES_PATH = os.path.join(os.path.dirname(__file__), "summaries_25.json")


# ---------------------------------------------------------------------------
# Summary system prompt
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """You are an insurance claims summarisation assistant.
Your job is to convert raw adjuster notes into a concise, structured claim summary
for claims operations routing.

OUTPUT FORMAT (always use exactly this structure):
Claim: [CLM-YYYY-NNNNN]
Date of Loss: [date]
Policy Form: [form number if mentioned]
Coverage Decision: [COVERED / DENIED / PENDING]
Deductible / Excess: [dollar amount or "N/A"]
Exclusion(s) Cited: [E-NN code(s) if denial, otherwise "N/A"]
Summary: [2-3 sentence narrative]

RULES:
1. Only use information present in the adjuster notes.
2. Do NOT invent policy clauses, exclusion codes, or dollar amounts not in the notes.
3. If the notes say denied with an exclusion, cite exactly that exclusion code.
4. Always echo the claim number exactly as given.
5. Always include the date of loss.
6. If a deductible/excess amount is mentioned, include the numeric value.
"""


def get_client() -> OpenAI:
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Export: export GROQ_API_KEY=gsk_..."
        )
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=60.0)


def generate_summary(case: dict, verbose: bool = True) -> str:
    """
    Generate a claim summary from adjuster notes.

    Args:
        case:    Eval case dict from eval_cases_25.jsonl
        verbose: Print progress

    Returns:
        The raw summary string produced by the LLM.
    """
    client = get_client()
    notes = case["adjuster_notes"]
    claim_number = case["claim_number"]

    user_message = (
        f"CLAIM NUMBER: {claim_number}\n\n"
        f"ADJUSTER NOTES:\n{notes}\n\n"
        "Write the structured claim summary following the required format."
    )

    response = client.chat.completions.create(
        model=SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        **SUMMARY_MODEL_PARAMS,
    )

    summary = response.choices[0].message.content.strip()

    if verbose:
        print(f"  Case {case['id']:02d} [{case['mode']:25s}]: {claim_number}")
        print(f"           Summary (first 120): {summary[:120]}...")

    return summary


def generate_all_summaries(
    cases: list[dict], verbose: bool = True, force_regen: bool = False
) -> dict[int, str]:
    """
    Generate summaries for all 25 cases. Saves to summaries_25.json.
    If the file already exists and force_regen=False, loads from disk.

    Returns: {case_id: summary_text}
    """
    if not force_regen and os.path.exists(SUMMARIES_PATH):
        with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        # json keys are strings — convert back to int
        summaries = {int(k): v for k, v in loaded.items()}
        if verbose:
            print(
                f"  ✅ Loaded {len(summaries)} existing summaries from summaries_25.json"
            )
        return summaries

    summaries: dict[int, str] = {}
    for case in cases:
        try:
            s = generate_summary(case, verbose=verbose)
            summaries[case["id"]] = s
        except Exception as e:
            print(f"  ❌ Case {case['id']} failed: {e}")
            summaries[case["id"]] = f"[GENERATION FAILED: {e}]"

    # Save to disk
    with open(SUMMARIES_PATH, "w", encoding="utf-8") as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"\n  ✅ {len(summaries)} summaries saved to week6/summaries_25.json")

    return summaries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    sys.path.insert(0, os.path.dirname(__file__))

    parser = argparse.ArgumentParser(description="Generate claim summaries for Week 6")
    parser.add_argument("--force", action="store_true", help="Force regeneration")
    args = parser.parse_args()

    # Load cases
    cases_path = os.path.join(os.path.dirname(__file__), "eval_cases_25.jsonl")
    cases = []
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    print(f"Loaded {len(cases)} cases.")
    summaries = generate_all_summaries(cases, verbose=True, force_regen=args.force)
    print(f"\n✅ Done. {len(summaries)} summaries generated.")
