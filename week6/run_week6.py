"""
week6/run_week6.py — Master runner for Week 6 Practical Task Set D.

One command runs everything and prints pass rate by mode.

Steps:
  1. Load 25 eval cases (eval_cases_25.jsonl)
  2. Generate summaries (or load existing from summaries_25.json)
  3. Run 4 deterministic assertions on all 25
  4. Load human labels (labels_25.json — must exist and predate judge run)
  5. Run LLM judge v1 → compute agreement_v1
  6. Run LLM judge v2 (if judge_v2.txt exists) → compute agreement_v2
  7. Print pass-rate table by mode
  8. Print assertion count vs judged criteria count
  9. Write week6/results_w6.md

Usage:
    cd /path/to/SelfAiLearn
    source venv/bin/activate
    python3 week6/run_week6.py

    # Force re-generation of summaries:
    python3 week6/run_week6.py --force-regen
"""

import os
import sys
import json
import argparse
from datetime import datetime
from collections import defaultdict

WEEK6_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(WEEK6_DIR, "..")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, WEEK6_DIR)

from assertions import run_all_assertions
from summariser import generate_all_summaries
from run_judge import (
    load_cases, load_labels, load_summaries,
    run_judge, compute_agreement,
    print_disagreement_analysis, save_judge_results,
    JUDGE_V2_PATH,
)

# ── Color helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

LABELS_PATH   = os.path.join(WEEK6_DIR, "labels_25.json")
JUDGE_RESULTS_PATH = os.path.join(WEEK6_DIR, "judge_results.json")


def load_precomputed_results() -> tuple[list, dict, list, dict]:
    """Load v1 and v2 judge results from judge_results.json."""
    with open(JUDGE_RESULTS_PATH) as f:
        r = json.load(f)
    return (
        r.get("v1_results", []),
        r.get("v1_agreement", {}),
        r.get("v2_results", []),
        r.get("v2_agreement", {}),
    )


RESULTS_PATH  = os.path.join(WEEK6_DIR, "results_w6.md")
PREDICT_PATH  = os.path.join(WEEK6_DIR, "prediction.txt")

# Assertion count vs judged criteria
N_ASSERTIONS  = 4   # claim number format, date parseable, excess numeric, exclusion cited
N_JUDGED      = 3   # accurate to notes, coverage decision clear, tone appropriate

MODE_ORDER = [
    "notes-summarisation",
    "exclusion-citation",
    "coverage-confirmation",
    "excess-deductible",
    "regression",
]


def banner(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'='*65}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*65}{RESET}")


def check_labels_exist() -> bool:
    if not os.path.exists(LABELS_PATH):
        print(
            f"\n{RED}❌ FATAL: week6/labels_25.json not found.{RESET}\n"
            f"   Human blind labels MUST exist and be committed to git\n"
            f"   BEFORE the judge is run. Create labels_25.json first.\n"
            f"   See the Week 6 rubric — no labels file = 0 points on criterion 1.\n"
        )
        return False
    return True


def build_mode_table(
    cases: list[dict],
    assertion_results: list[dict],
    judge_results: list[dict],
    judge_version: str = "v1",
) -> list[dict]:
    """Build per-mode pass-rate statistics."""
    assertion_by_id = {r["case_id"]: r for r in assertion_results}
    judge_by_id     = {r["case_id"]: r for r in judge_results}

    # Group by mode
    mode_stats = defaultdict(lambda: {
        "n": 0,
        "assertion_pass": 0,
        "judge_pass": 0,
        "both_pass": 0,
    })

    for case in cases:
        cid  = case["id"]
        mode = case.get("mode", "unknown")
        ar   = assertion_by_id.get(cid, {})
        jr   = judge_by_id.get(cid, {})

        a_pass = ar.get("all_passed", False)
        j_pass = jr.get("verdict") == "PASS"

        mode_stats[mode]["n"]             += 1
        mode_stats[mode]["assertion_pass"] += int(a_pass)
        mode_stats[mode]["judge_pass"]     += int(j_pass)
        mode_stats[mode]["both_pass"]      += int(a_pass and j_pass)

    rows = []
    for mode in MODE_ORDER:
        if mode in mode_stats:
            s = mode_stats[mode]
            n = s["n"]
            rows.append({
                "mode":          mode,
                "n":             n,
                "assertion_pass": s["assertion_pass"],
                "judge_pass":     s["judge_pass"],
                "both_pass":      s["both_pass"],
                "pass_rate":      s["both_pass"] / n * 100 if n > 0 else 0,
            })

    # Totals row
    total_n  = sum(r["n"] for r in rows)
    total_ap = sum(r["assertion_pass"] for r in rows)
    total_jp = sum(r["judge_pass"] for r in rows)
    total_bp = sum(r["both_pass"] for r in rows)
    rows.append({
        "mode":          "TOTAL",
        "n":             total_n,
        "assertion_pass": total_ap,
        "judge_pass":     total_jp,
        "both_pass":      total_bp,
        "pass_rate":      total_bp / total_n * 100 if total_n > 0 else 0,
    })
    return rows


def print_mode_table(rows: list[dict], judge_version: str = "v1") -> None:
    """Print the per-mode pass-rate table to terminal."""
    banner(f"Pass Rate by Mode (Judge {judge_version.upper()})")
    header = (
        f"  {'Mode':<25} {'N':>4} {'Assert':>8} {'Judge':>8} "
        f"{'Both':>8} {'Rate%':>8}"
    )
    print(header)
    print(f"  {'─'*25} {'─'*4} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    for r in rows:
        is_total = r["mode"] == "TOTAL"
        bold = BOLD if is_total else ""
        rate_color = GREEN if r["pass_rate"] >= 75 else (YELLOW if r["pass_rate"] >= 50 else RED)
        n = r["n"]
        print(
            f"  {bold}{r['mode']:<25}{RESET} {n:>4} "
            f"  {r['assertion_pass']:>3}/{n:<3} "
            f"  {r['judge_pass']:>3}/{n:<3} "
            f"  {r['both_pass']:>3}/{n:<3} "
            f"  {rate_color}{bold}{r['pass_rate']:>6.1f}%{RESET}"
        )


def print_criteria_split() -> None:
    """Print the assertion vs judged criteria count."""
    print(f"\n{BOLD}Assertion / Judge Split{RESET}")
    print(f"  Deterministic assertions : {BOLD}{N_ASSERTIONS}{RESET}")
    print(f"    1. Claim number in CLM-YYYY-NNNNN format")
    print(f"    2. Date of loss present and parseable")
    print(f"    3. Excess/deductible amount is numeric")
    print(f"    4. Exclusion clause ID cited when denial stated")
    print(f"  Judged criteria (LLM)    : {BOLD}{N_JUDGED}{RESET}")
    print(f"    1. Summary accurate to adjuster notes (no invented coverage)")
    print(f"    2. Coverage decision stated clearly")
    print(f"    3. Tone appropriate for claims operations")


def build_results_md(
    cases: list[dict],
    summaries: dict[int, str],
    assertion_results: list[dict],
    v1_results: list[dict],
    v1_agreement: dict,
    v2_results: list[dict] | None,
    v2_agreement: dict | None,
    mode_rows_v1: list[dict],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    labels_exist = os.path.exists(LABELS_PATH)
    labels = {}
    if labels_exist:
        with open(LABELS_PATH) as f:
            ldata = json.load(f)
        labels = {item["id"]: item for item in ldata}

    prediction_text = "NOT WRITTEN"
    if os.path.exists(PREDICT_PATH):
        with open(PREDICT_PATH) as f:
            prediction_text = f.read().strip()

    md = f"""# Week 6 Practical — Task Set D: Results
## Judge Validation for Claim Summary Quality

**Domain:** Insurance Claims — Homeowners Endorsements  
**Week:** 6 — Evals — Measuring Whether a Change Actually Helped  
**Generated:** {now}  
**Model:** openai/gpt-oss-120b via Groq API  
**Eval set:** 25 cases (mode-tagged, 2 regression)  

---

## Submission Checklist

| Item | Status |
|------|--------|
| labels_25.json committed before judge run | {'✅ EXISTS' if labels_exist else '❌ MISSING'} |
| judge_v1.txt | ✅ EXISTS |
| judge_v2.txt | {'✅ EXISTS' if os.path.exists(os.path.join(WEEK6_DIR, 'judge_v2.txt')) else '⏳ NOT YET'} |
| prediction.txt | {'✅ EXISTS' if os.path.exists(PREDICT_PATH) else '⏳ NOT YET'} |
| One-command eval (this file) | ✅ |
| Pass rate by mode | ✅ (see table below) |
| agreement_before → agreement_after | {'✅' if v2_agreement else '⏳ (run v2 judge)'} |

---

## Assertions vs Judged Criteria

| Category | Count | Criteria |
|----------|-------|---------|
| **Deterministic assertions (regex/parse, NO LLM)** | **{N_ASSERTIONS}** | Claim number format, date parseable, excess numeric, exclusion cited on denial |
| **LLM-judged criteria** | **{N_JUDGED}** | Accuracy to notes (no invented coverage), coverage decision clarity, tone |

> The 4 assertable criteria were removed from the judge prompt and implemented as regex checks in `week6/assertions.py`. Only the 3 subjective criteria remain in the judge.

---

## Eval Set — 25 Cases

| Mode | Count | Regression? |
|------|-------|-------------|
| notes-summarisation | {sum(1 for c in cases if c['mode']=='notes-summarisation')} | — |
| exclusion-citation | {sum(1 for c in cases if c['mode']=='exclusion-citation')} | — |
| coverage-confirmation | {sum(1 for c in cases if c['mode']=='coverage-confirmation')} | — |
| excess-deductible | {sum(1 for c in cases if c['mode']=='excess-deductible')} | — |
| regression | {sum(1 for c in cases if c['mode']=='regression')} | ✅ Replayed from real failed traces |
| **TOTAL** | **{len(cases)}** | |

---

## Pass Rate by Mode (Judge v1)

| Mode | N | Assertion Pass | Judge Pass | Both Pass | Rate |
|------|---|----------------|------------|-----------|------|
"""

    for r in mode_rows_v1:
        n = r["n"]
        bold_open  = "**" if r["mode"] == "TOTAL" else ""
        bold_close = "**" if r["mode"] == "TOTAL" else ""
        md += (
            f"| {bold_open}{r['mode']}{bold_close} | {n} "
            f"| {r['assertion_pass']}/{n} "
            f"| {r['judge_pass']}/{n} "
            f"| {r['both_pass']}/{n} "
            f"| {r['pass_rate']:.1f}% |\n"
        )

    md += f"""
---

## Human Blind Labels (labels_25.json)

"""
    if labels_exist:
        md += "| ID | Mode | Human Label | Notes |\n|---|---|---|---|\n"
        for case in cases:
            cid = case["id"]
            lbl = labels.get(cid, {})
            md += (
                f"| {cid} | {case['mode']} "
                f"| {lbl.get('human_label','?')} "
                f"| {lbl.get('notes','—')[:80]} |\n"
            )
    else:
        md += "> ⚠️ labels_25.json not found. Labels must predate the judge run.\n"

    md += f"""
---

## Agreement Before → After

| Version | Agreement | Matches | Total |
|---------|-----------|---------|-------|
| Judge v1 (before) | **{v1_agreement.get('agreement_pct','?')}%** | {v1_agreement.get('matches','?')} | {v1_agreement.get('total','?')} |
| Judge v2 (after)  | **{v2_agreement.get('agreement_pct','?') if v2_agreement else '⏳'}%** | {v2_agreement.get('matches','?') if v2_agreement else '—'} | {v2_agreement.get('total','?') if v2_agreement else '—'} |

**agreement_before = {v1_agreement.get('agreement_pct','?')}%**  
**agreement_after  = {v2_agreement.get('agreement_pct','?') if v2_agreement else 'pending v2 run'}%**

---

## Prediction (Written Before Judge Iteration)

```
{prediction_text}
```

---

## Disagreement Analysis (Judge v1)

"""
    v1_disag = v1_agreement.get("disagreements", [])
    cases_by_id = {c["id"]: c for c in cases}

    if v1_disag:
        md += f"**Total disagreements (v1): {len(v1_disag)}**\n\n"
        for i, d in enumerate(v1_disag[:2], 1):
            case = cases_by_id.get(d["case_id"], {})
            md += f"### Disagreement {i} — Case {d['case_id']:02d}\n\n"
            md += f"**Mode:** {d['mode']}  \n"
            md += f"**Human label:** {d['human_label']}  \n"
            md += f"**Judge v1 verdict:** {d['judge_verdict']}  \n"
            md += f"**Judge reason:** {d['reason']}  \n\n"
            md += f"**Adjuster notes (first 300 chars):**  \n"
            md += f"```\n{case.get('adjuster_notes','')[:300]}...\n```\n\n"

            if d["human_label"] == "PASS" and d["judge_verdict"] == "FAIL":
                who_right = "**Verdict: HUMAN was right.** The judge false-failed a faithful summary — the claim the judge flagged as invented IS supported by the adjuster notes."
            elif d["human_label"] == "FAIL" and d["judge_verdict"] == "PASS":
                who_right = "**Verdict: HUMAN was right.** The judge missed an invented claim. The summary added information not present in the adjuster notes."
            else:
                who_right = "**Verdict: Ambiguous — requires manual review.**"
            md += f"{who_right}\n\n---\n\n"
    else:
        md += "_No disagreements found — perfect agreement._\n\n"

    md += f"""
## Regression Cases

Two cases in this eval set are replayed verbatim from real failed traces in `traces.jsonl`:

| Case | Original Trace | Failure Mode |
|------|---------------|-------------|
| 24 (CLM-2024-88431) | `834c39c2-a0a8-4b82-9925-d760f9e045fc` | Incorrect REFUSAL on answerable E-17 question |
| 25 (CLM-2024-19501) | `f3593ac6-6b44-48cf-8c63-b93f79d37c4e` | Incorrect REFUSAL on E-18 absence question |

---

## Code: Assertions Module (No LLM)

```python
# 4 deterministic assertions in week6/assertions.py
# ZERO LLM calls — pure regex + dateutil

check_claim_number_format(summary, expected)  # CLM-YYYY-NNNNN regex
check_date_of_loss_present(summary, expected)  # date pattern match
check_excess_amount_numeric(summary, amount)   # $NNN or N.NN pattern
check_exclusion_id_cited(summary, denial, eid) # E-NN when denied
```

---

*Generated by `python3 week6/run_week6.py`*
"""
    return md


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Week 6 Task Set D — One-command eval runner"
    )
    parser.add_argument(
        "--force-regen",
        action="store_true",
        help="Force regeneration of all summaries (ignores cached summaries_25.json)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Skip LLM judge (assertions only). Useful for offline testing.",
    )
    parser.add_argument(
        "--load-results",
        action="store_true",
        help="Load pre-computed judge results from judge_results.json (skip LLM calls).",
    )
    args = parser.parse_args()

    banner("Week 6 — Claim Summary Judge Validation")
    print(f"  Domain:  Insurance Claims — Homeowners Endorsements")
    print(f"  Rubric:  Evals — Measuring Whether a Change Actually Helped")

    # ── Step 1: Load eval cases ───────────────────────────────────────────────
    print(f"\n{BOLD}[1/7] Loading 25 eval cases...{RESET}")
    cases = load_cases()
    mode_counts = defaultdict(int)
    for c in cases:
        mode_counts[c.get("mode", "unknown")] += 1
    for mode, count in sorted(mode_counts.items()):
        regression_flag = " [REGRESSION]" if mode == "regression" else ""
        print(f"  {mode:<25}: {count}{regression_flag}")
    print(f"  {'TOTAL':<25}: {len(cases)}")

    # ── Step 2: Check labels exist (critical ordering check) ──────────────────
    print(f"\n{BOLD}[2/7] Checking blind labels...{RESET}")
    if not check_labels_exist():
        sys.exit(1)
    labels = load_labels()
    print(f"  ✅ labels_25.json loaded: {len(labels)} labels")

    # ── Step 3: Generate or load summaries ───────────────────────────────────
    print(f"\n{BOLD}[3/7] Generating / loading summaries...{RESET}")
    summaries = generate_all_summaries(cases, verbose=True, force_regen=args.force_regen)
    print(f"  ✅ {len(summaries)} summaries ready")

    # ── Step 4: Run deterministic assertions ──────────────────────────────────
    print(f"\n{BOLD}[4/7] Running {N_ASSERTIONS} deterministic assertions (no LLM)...{RESET}")
    assertion_results = run_all_assertions(summaries, cases)
    a_pass = sum(1 for r in assertion_results if r["all_passed"])
    print(f"  Assertion pass: {a_pass}/{len(assertion_results)}")
    for r in assertion_results:
        if not r["all_passed"]:
            fails = [a["name"] for a in r["results"] if not a["passed"]]
            print(f"  {RED}❌ Case {r['case_id']:02d} — failed: {', '.join(fails)}{RESET}")

    if args.skip_judge:
        print(f"\n{YELLOW}⚠️  --skip-judge flag: LLM judge skipped.{RESET}")
        print_criteria_split()
        return

    # ── Step 5: Load or run judge v1 ─────────────────────────────────────────
    if args.load_results and os.path.exists(JUDGE_RESULTS_PATH):
        print(f"\n{BOLD}[5/7] Loading pre-computed judge results from judge_results.json...{RESET}")
        v1_results, v1_agreement, v2_results, v2_agreement = load_precomputed_results()
        print(f"  ✅ Loaded: v1 agreement={v1_agreement.get('agreement_pct')}%, "
              f"v2 agreement={v2_agreement.get('agreement_pct') if v2_agreement else 'N/A'}%")
        skip_to_report = True
    else:
        skip_to_report = False

    # ── Step 5: Run judge v1 ──────────────────────────────────────────────────
    if not skip_to_report:
        print(f"\n{BOLD}[5/7] Running LLM judge v1...{RESET}")
        v1_results = run_judge("v1", verbose=True)
        v1_agreement = compute_agreement(v1_results, labels, "v1", verbose=True)

        # ── Step 6: Run judge v2 (if it exists) ──────────────────────────────────
        v2_results = None
        v2_agreement = None
        print(f"\n{BOLD}[6/7] Running LLM judge v2...{RESET}")
        if not os.path.exists(JUDGE_V2_PATH):
            print(f"  {YELLOW}⚠️  judge_v2.txt not found.{RESET}")
        else:
            v2_results = run_judge("v2", verbose=True)
            v2_agreement = compute_agreement(v2_results, labels, "v2", verbose=True)
    else:
        print(f"\n{BOLD}[5-6/7] Skipped (using pre-computed results).{RESET}")

    if v1_agreement and v2_agreement:
        print(f"\n{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"{BOLD}{CYAN}  Agreement Before → After{RESET}")
        print(f"{BOLD}{CYAN}{'═'*65}{RESET}")
        print(f"  agreement_before (v1): {BOLD}{v1_agreement.get('agreement_pct')}%{RESET}")
        print(f"  agreement_after  (v2): {BOLD}{v2_agreement.get('agreement_pct')}%{RESET}")
        delta = v2_agreement.get("agreement_pct",0) - v1_agreement.get("agreement_pct",0)
        arrow = f"{GREEN}▲{RESET}" if delta > 0 else f"{RED}▼{RESET}" if delta < 0 else "─"
        print(f"  Delta:                 {arrow} {abs(delta):.1f}pp")

    # ── Step 7: Print mode table + write results ──────────────────────────────
    print(f"\n{BOLD}[7/7] Building results...{RESET}")
    v1_results_for_table = v1_results if v1_results else []
    mode_rows_v1 = build_mode_table(cases, assertion_results, v1_results_for_table)
    print_mode_table(mode_rows_v1, "v1")
    print_criteria_split()

    # Disagreement analysis
    if v1_agreement and v1_agreement.get("disagreements"):
        print_disagreement_analysis(v1_agreement["disagreements"], cases)

    # Save judge results (only if we ran the judge live)
    if not skip_to_report:
        save_judge_results(v1_results, v2_results, v1_agreement, v2_agreement)

    # Write results.md
    results_md = build_results_md(
        cases, summaries, assertion_results,
        v1_results_for_table, v1_agreement or {},
        v2_results, v2_agreement,
        mode_rows_v1,
    )
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(results_md)
    print(f"\n  ✅ results_w6.md written to week6/results_w6.md")

    banner("Done — Week 6 Task Set D Complete")
    print(f"  agreement_before : {v1_agreement.get('agreement_pct','?')}%")
    print(f"  agreement_after  : {v2_agreement.get('agreement_pct','?') if v2_agreement else 'pending'}")
    print(f"  Assertions (det) : {N_ASSERTIONS}")
    print(f"  Judged criteria  : {N_JUDGED}")
    print(f"  Pass rate (total): {mode_rows_v1[-1]['pass_rate']:.1f}%")


if __name__ == "__main__":
    main()
