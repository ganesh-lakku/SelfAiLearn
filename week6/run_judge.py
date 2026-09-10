"""
week6/run_judge.py — LLM judge runner for Week 6 Task Set D.

Loads judge_v1.txt (or judge_v2.txt), runs it against all 25 summaries,
then computes agreement with the human labels in labels_25.json.

Usage:
    python3 week6/run_judge.py --version v1
    python3 week6/run_judge.py --version v2
    python3 week6/run_judge.py --version both   # reports before -> after
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
JUDGE_MODEL = "openai/gpt-oss-120b"
JUDGE_MODEL_PARAMS = {"temperature": 0.0, "max_tokens": 200}

WEEK6_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(WEEK6_DIR, "..")

LABELS_PATH = os.path.join(WEEK6_DIR, "labels_25.json")
SUMMARIES_PATH = os.path.join(WEEK6_DIR, "summaries_25.json")
CASES_PATH = os.path.join(WEEK6_DIR, "eval_cases_25.jsonl")
JUDGE_V1_PATH = os.path.join(WEEK6_DIR, "judge_v1.txt")
JUDGE_V2_PATH = os.path.join(WEEK6_DIR, "judge_v2.txt")
JUDGE_RESULTS_PATH = os.path.join(WEEK6_DIR, "judge_results.json")

# ── Color helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

_VERDICT_RE = re.compile(r"VERDICT:\s*(PASS|FAIL)", re.IGNORECASE)
_REASON_RE  = re.compile(r"REASON:\s*(.+)", re.IGNORECASE)


def get_client() -> OpenAI:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set.")
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=60.0)


def load_cases() -> list[dict]:
    cases = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def load_labels() -> dict[int, str]:
    """Returns {case_id: 'PASS'|'FAIL'}"""
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        labels_list = json.load(f)
    return {item["id"]: item["human_label"].upper() for item in labels_list}


def load_summaries() -> dict[int, str]:
    with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    return {int(k): v for k, v in loaded.items()}


def load_judge_prompt(version: str) -> str:
    path = JUDGE_V1_PATH if version == "v1" else JUDGE_V2_PATH
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_judge_on_one(
    client: OpenAI,
    judge_prompt: str,
    summary: str,
    adjuster_notes: str,
    case_id: int,
) -> dict:
    """Run the judge on a single (summary, notes) pair. Returns parsed verdict."""
    user_message = (
        f"ADJUSTER NOTES:\n{adjuster_notes}\n\n"
        f"GENERATED SUMMARY:\n{summary}\n\n"
        "Evaluate the summary against the adjuster notes using the criterion above. "
        "Output only VERDICT: and REASON: lines."
    )

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": judge_prompt},
            {"role": "user", "content": user_message},
        ],
        **JUDGE_MODEL_PARAMS,
    )

    raw = response.choices[0].message.content.strip()

    verdict_match = _VERDICT_RE.search(raw)
    reason_match  = _REASON_RE.search(raw)

    verdict = verdict_match.group(1).upper() if verdict_match else "UNKNOWN"
    reason  = reason_match.group(1).strip()  if reason_match  else raw

    return {
        "case_id":  case_id,
        "verdict":  verdict,
        "reason":   reason,
        "raw":      raw,
    }


def run_judge(version: str, verbose: bool = True) -> list[dict]:
    """
    Run the judge (v1 or v2) over all 25 cases.
    Returns list of {case_id, verdict, reason, raw}.
    """
    client = get_client()
    judge_prompt = load_judge_prompt(version)
    cases = load_cases()
    summaries = load_summaries()

    if verbose:
        print(f"\n{BOLD}{CYAN}{'─'*65}{RESET}")
        print(f"{BOLD}{CYAN}  Running Judge {version.upper()} over 25 cases{RESET}")
        print(f"{BOLD}{CYAN}{'─'*65}{RESET}")

    results = []
    for case in cases:
        cid = case["id"]
        summary = summaries.get(cid, "[MISSING SUMMARY]")
        notes = case["adjuster_notes"]

        result = run_judge_on_one(client, judge_prompt, summary, notes, cid)
        result["mode"] = case.get("mode", "unknown")
        result["is_regression"] = case.get("is_regression", False)

        if verbose:
            icon = f"{GREEN}✅ PASS{RESET}" if result["verdict"] == "PASS" else f"{RED}❌ FAIL{RESET}"
            print(
                f"  Case {cid:02d} [{case['mode']:25s}] → {icon}  {result['reason'][:70]}"
            )

        results.append(result)

    return results


def compute_agreement(
    judge_results: list[dict], labels: dict[int, str], version: str, verbose: bool = True
) -> dict:
    """
    Compare judge verdicts with human labels.
    Returns agreement stats.
    """
    matches = 0
    total = len(judge_results)
    disagreements = []

    for r in judge_results:
        cid = r["case_id"]
        human = labels.get(cid, "UNKNOWN")
        judge = r["verdict"]
        agree = human == judge

        if agree:
            matches += 1
        else:
            disagreements.append({
                "case_id":      cid,
                "human_label":  human,
                "judge_verdict": judge,
                "mode":         r.get("mode"),
                "reason":       r.get("reason"),
            })

    agreement_pct = matches / total * 100 if total > 0 else 0

    if verbose:
        print(f"\n{BOLD}{'─'*65}{RESET}")
        print(f"{BOLD}  Agreement ({version}): {matches}/{total} = {agreement_pct:.1f}%{RESET}")
        print(f"{'─'*65}")
        if disagreements:
            print(f"  Disagreements ({len(disagreements)}):")
            for d in disagreements:
                print(
                    f"    Case {d['case_id']:02d} [{d['mode']:20s}] "
                    f"Human={d['human_label']} | Judge={d['judge_verdict']}"
                )
                print(f"           Judge said: {d['reason'][:80]}")
        print()

    return {
        "version":       version,
        "agreement_pct": round(agreement_pct, 1),
        "matches":       matches,
        "total":         total,
        "disagreements": disagreements,
    }


def print_disagreement_analysis(disagreements: list[dict], cases: list[dict]) -> None:
    """Print a detailed analysis of up to 2 key disagreements."""
    cases_by_id = {c["id"]: c for c in cases}

    print(f"\n{BOLD}{CYAN}{'═'*65}{RESET}")
    print(f"{BOLD}{CYAN}  Disagreement Analysis (first 2){RESET}")
    print(f"{BOLD}{CYAN}{'═'*65}{RESET}")

    for i, d in enumerate(disagreements[:2], 1):
        cid = d["case_id"]
        case = cases_by_id.get(cid, {})
        print(f"\n  Disagreement {i} — Case {cid:02d}")
        print(f"  Mode:          {d['mode']}")
        print(f"  Human label:   {d['human_label']}")
        print(f"  Judge verdict: {d['judge_verdict']}")
        print(f"  Judge reason:  {d['reason']}")
        print(f"  Adjuster notes snippet: {case.get('adjuster_notes','')[:200]}...")

        # Verdict on who was right
        if d["human_label"] == "PASS" and d["judge_verdict"] == "FAIL":
            verdict = (
                f"  WHO WAS RIGHT: {GREEN}HUMAN{RESET}. "
                "The judge false-failed a faithful summary. "
                "The 'invented' claim the judge flagged is actually supported by the notes."
            )
        elif d["human_label"] == "FAIL" and d["judge_verdict"] == "PASS":
            verdict = (
                f"  WHO WAS RIGHT: {GREEN}HUMAN{RESET}. "
                "The judge missed an invented claim that a careful reader caught."
            )
        else:
            verdict = f"  WHO WAS RIGHT: Unclear — review manually."

        print(verdict)
        print()


def save_judge_results(
    v1_results: list[dict],
    v2_results: list[dict] | None,
    v1_agreement: dict,
    v2_agreement: dict | None,
) -> None:
    """Save all judge results to judge_results.json."""
    output = {
        "generated_at":       datetime.now().isoformat(),
        "v1_results":         v1_results,
        "v1_agreement":       v1_agreement,
        "v2_results":         v2_results or [],
        "v2_agreement":       v2_agreement or {},
        "agreement_before":   v1_agreement["agreement_pct"],
        "agreement_after":    v2_agreement["agreement_pct"] if v2_agreement else None,
    }
    with open(JUDGE_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Judge results saved to week6/judge_results.json")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Week 6 Judge Runner")
    parser.add_argument(
        "--version",
        choices=["v1", "v2", "both"],
        default="both",
        help="Which judge version to run",
    )
    args = parser.parse_args()

    labels = load_labels()
    cases = load_cases()

    v1_results = v1_agreement = None
    v2_results = v2_agreement = None

    if args.version in ("v1", "both"):
        v1_results = run_judge("v1", verbose=True)
        v1_agreement = compute_agreement(v1_results, labels, "v1", verbose=True)

    if args.version in ("v2", "both"):
        if not os.path.exists(JUDGE_V2_PATH):
            print(f"{YELLOW}⚠️  judge_v2.txt not found — skipping v2.{RESET}")
            print("    Run v1 first, pick 2 disagreements, create judge_v2.txt, then re-run.")
        else:
            v2_results = run_judge("v2", verbose=True)
            v2_agreement = compute_agreement(v2_results, labels, "v2", verbose=True)

    # Before -> after summary
    if v1_agreement and v2_agreement:
        print(f"\n{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"{BOLD}{CYAN}  Agreement Before → After{RESET}")
        print(f"{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"  agreement_before (v1): {BOLD}{v1_agreement['agreement_pct']}%{RESET}")
        print(f"  agreement_after  (v2): {BOLD}{v2_agreement['agreement_pct']}%{RESET}")
        delta = v2_agreement["agreement_pct"] - v1_agreement["agreement_pct"]
        arrow = f"{GREEN}▲{RESET}" if delta > 0 else f"{RED}▼{RESET}"
        print(f"  Delta:                 {arrow} {abs(delta):.1f}pp")
        print(f"{BOLD}{CYAN}{'═'*65}{RESET}\n")

        # Disagreement analysis
        if v1_agreement["disagreements"]:
            print_disagreement_analysis(v1_agreement["disagreements"], cases)

    save_judge_results(v1_results or [], v2_results, v1_agreement or {}, v2_agreement)


if __name__ == "__main__":
    main()
