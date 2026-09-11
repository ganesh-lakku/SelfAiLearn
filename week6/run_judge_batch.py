"""
week6/run_judge_batch.py — Batched LLM judge runner for Week 6 Task Set D.

Instead of 25 sequential API calls (rate-limit prone), this packs all 25
(adjuster_notes, summary) pairs into ONE prompt and gets all verdicts back
in a single response. Much faster and avoids rate-limit empty responses.

Usage:
    python3 week6/run_judge_batch.py --version v1
    python3 week6/run_judge_batch.py --version v2
    python3 week6/run_judge_batch.py --version both
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
JUDGE_MODEL   = "openai/gpt-oss-20b"
JUDGE_MODEL_PARAMS = {"temperature": 0.0, "max_tokens": 8000}

WEEK6_DIR    = os.path.dirname(os.path.abspath(__file__))
LABELS_PATH  = os.path.join(WEEK6_DIR, "labels_25.json")
SUMMARIES_PATH = os.path.join(WEEK6_DIR, "summaries_25.json")
CASES_PATH   = os.path.join(WEEK6_DIR, "eval_cases_25.jsonl")
JUDGE_V1_PATH = os.path.join(WEEK6_DIR, "judge_v1.txt")
JUDGE_V2_PATH = os.path.join(WEEK6_DIR, "judge_v2.txt")
JUDGE_RESULTS_PATH = os.path.join(WEEK6_DIR, "judge_results.json")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# Parse "CASE-01: PASS|FAIL" lines from batched response
_BATCH_LINE_RE = re.compile(
    r"CASE-(\d+):\s*\*{0,2}(PASS|FAIL)\*{0,2}\s*[|\-–]\s*(.+?)(?=\nCASE-|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def get_client() -> OpenAI:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set.")
    return OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=120.0)


def load_cases() -> list[dict]:
    cases = []
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def load_labels() -> dict[int, str]:
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


def build_batch_user_message(cases: list[dict], summaries: dict[int, str]) -> str:
    """Pack all 25 (notes, summary) pairs into one user message."""
    lines = [
        "Evaluate each case below using the criterion in your system prompt.\n"
        "For EACH case output EXACTLY one line in this format:\n"
        "CASE-NN: PASS | one-sentence reason\n"
        "or\n"
        "CASE-NN: FAIL | one-sentence reason\n\n"
        "Output ONLY the CASE-NN lines, nothing else.\n"
        "---\n"
    ]
    for case in cases:
        cid = case["id"]
        notes   = case["adjuster_notes"]
        summary = summaries.get(cid, "[MISSING]")
        lines.append(f"CASE-{cid:02d}:\nADJUSTER NOTES: {notes}\nGENERATED SUMMARY: {summary}\n")

    return "\n".join(lines)


def parse_batch_response(raw: str, cases: list[dict]) -> list[dict]:
    """Parse 'CASE-NN: PASS|FAIL | reason' lines from batch response."""
    case_ids = {c["id"] for c in cases}
    case_map = {c["id"]: c for c in cases}

    results: dict[int, dict] = {}

    for m in _BATCH_LINE_RE.finditer(raw):
        cid_str, verdict, reason = m.group(1), m.group(2).upper(), m.group(3).strip()
        cid = int(cid_str)
        results[cid] = {
            "case_id": cid,
            "verdict": verdict,
            "reason":  reason[:200],
            "raw":     m.group(0),
            "mode":    case_map.get(cid, {}).get("mode", "unknown"),
            "is_regression": case_map.get(cid, {}).get("is_regression", False),
        }

    # Fill missing with UNKNOWN
    for cid in sorted(case_ids):
        if cid not in results:
            results[cid] = {
                "case_id": cid,
                "verdict": "UNKNOWN",
                "reason":  "[not found in batch response]",
                "raw":     "",
                "mode":    case_map.get(cid, {}).get("mode", "unknown"),
                "is_regression": case_map.get(cid, {}).get("is_regression", False),
            }

    return [results[cid] for cid in sorted(results.keys())]


def run_judge_batch(version: str, verbose: bool = True) -> list[dict]:
    """Run the judge over all 25 cases in a single API call."""
    client = get_client()
    judge_prompt = load_judge_prompt(version)
    cases    = load_cases()
    summaries = load_summaries()

    if verbose:
        print(f"\n{BOLD}{CYAN}{'─'*65}{RESET}")
        print(f"{BOLD}{CYAN}  Running Judge {version.upper()} (batch) — 1 API call for all 25{RESET}")
        print(f"{BOLD}{CYAN}{'─'*65}{RESET}")

    user_msg = build_batch_user_message(cases, summaries)

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[
            {"role": "system", "content": judge_prompt},
            {"role": "user",   "content": user_msg},
        ],
        **JUDGE_MODEL_PARAMS,
    )

    raw = response.choices[0].message.content.strip()

    if verbose:
        print(f"  Raw response ({len(raw)} chars):")
        print(f"  {raw[:600]}...")

    results = parse_batch_response(raw, cases)

    if verbose:
        print()
        for r in results:
            v = r["verdict"]
            icon = f"{GREEN}✅ PASS{RESET}" if v == "PASS" else (
                   f"{RED}❌ FAIL{RESET}" if v == "FAIL" else f"{YELLOW}⚠️  {v}{RESET}")
            print(f"  Case {r['case_id']:02d} [{r['mode']:25s}] → {icon}  {r['reason'][:65]}")

    return results


def compute_agreement(
    judge_results: list[dict], labels: dict[int, str], version: str, verbose: bool = True
) -> dict:
    matches = 0
    total = len(judge_results)
    disagreements = []

    for r in judge_results:
        cid   = r["case_id"]
        human = labels.get(cid, "UNKNOWN")
        judge = r["verdict"]
        agree = human == judge

        if agree:
            matches += 1
        else:
            disagreements.append({
                "case_id":       cid,
                "human_label":   human,
                "judge_verdict": judge,
                "mode":          r.get("mode"),
                "reason":        r.get("reason"),
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
                print(f"           Judge: {d['reason'][:80]}")
        print()

    return {
        "version":       version,
        "agreement_pct": round(agreement_pct, 1),
        "matches":       matches,
        "total":         total,
        "disagreements": disagreements,
    }


def save_results(
    v1_results, v2_results, v1_agreement, v2_agreement,
    v1_raw_response: str = "", v2_raw_response: str = ""
) -> None:
    output = {
        "generated_at":     datetime.now().isoformat(),
        "judge_model":      JUDGE_MODEL,
        "v1_results":       v1_results,
        "v1_agreement":     v1_agreement,
        "v1_raw_response":  v1_raw_response,
        "v2_results":       v2_results or [],
        "v2_agreement":     v2_agreement or {},
        "v2_raw_response":  v2_raw_response,
        "agreement_before": v1_agreement.get("agreement_pct"),
        "agreement_after":  v2_agreement.get("agreement_pct") if v2_agreement else None,
    }
    with open(JUDGE_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  ✅ Judge results saved to week6/judge_results.json")


def main():
    parser = argparse.ArgumentParser(description="Week 6 Batch Judge Runner")
    parser.add_argument("--version", choices=["v1", "v2", "both"], default="both")
    args = parser.parse_args()

    labels = load_labels()

    v1_results = v1_agreement = None
    v2_results = v2_agreement = None
    v1_raw = v2_raw = ""

    if args.version in ("v1", "both"):
        v1_results = run_judge_batch("v1", verbose=True)
        v1_agreement = compute_agreement(v1_results, labels, "v1", verbose=True)

    if args.version in ("v2", "both"):
        if not os.path.exists(JUDGE_V2_PATH):
            print(f"\n{YELLOW}⚠️  judge_v2.txt not found — skipping v2.{RESET}")
        else:
            v2_results = run_judge_batch("v2", verbose=True)
            v2_agreement = compute_agreement(v2_results, labels, "v2", verbose=True)

    if v1_agreement and v2_agreement:
        print(f"\n{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"{BOLD}{CYAN}  Agreement Before → After{RESET}")
        print(f"{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"  agreement_before (v1): {BOLD}{v1_agreement['agreement_pct']}%{RESET}")
        print(f"  agreement_after  (v2): {BOLD}{v2_agreement['agreement_pct']}%{RESET}")
        delta = v2_agreement["agreement_pct"] - v1_agreement["agreement_pct"]
        arrow = f"{GREEN}▲{RESET}" if delta > 0 else f"{RED}▼{RESET}" if delta < 0 else "─"
        print(f"  Delta:                 {arrow} {abs(delta):.1f}pp")

    save_results(v1_results or [], v2_results, v1_agreement or {}, v2_agreement, v1_raw, v2_raw)


if __name__ == "__main__":
    main()
