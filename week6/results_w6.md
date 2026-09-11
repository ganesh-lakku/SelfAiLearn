# Week 6 Practical — Task Set D: Results
## Judge Validation for Claim Summary Quality

**Domain:** Insurance Claims — Homeowners Endorsements  
**Week:** 6 — Evals — Measuring Whether a Change Actually Helped  
**Generated:** 2026-09-11 12:26:02  
**Model:** openai/gpt-oss-120b via Groq API  
**Eval set:** 25 cases (mode-tagged, 2 regression)  

---

## Submission Checklist

| Item | Status |
|------|--------|
| labels_25.json committed before judge run | ✅ EXISTS |
| judge_v1.txt | ✅ EXISTS |
| judge_v2.txt | ✅ EXISTS |
| prediction.txt | ✅ EXISTS |
| One-command eval (this file) | ✅ |
| Pass rate by mode | ✅ (see table below) |
| agreement_before → agreement_after | ✅ |

---

## Assertions vs Judged Criteria

| Category | Count | Criteria |
|----------|-------|---------|
| **Deterministic assertions (regex/parse, NO LLM)** | **4** | Claim number format, date parseable, excess numeric, exclusion cited on denial |
| **LLM-judged criteria** | **3** | Accuracy to notes (no invented coverage), coverage decision clarity, tone |

> The 4 assertable criteria were removed from the judge prompt and implemented as regex checks in `week6/assertions.py`. Only the 3 subjective criteria remain in the judge.

---

## Eval Set — 25 Cases

| Mode | Count | Regression? |
|------|-------|-------------|
| notes-summarisation | 6 | — |
| exclusion-citation | 9 | — |
| coverage-confirmation | 5 | — |
| excess-deductible | 3 | — |
| regression | 2 | ✅ Replayed from real failed traces |
| **TOTAL** | **25** | |

---

## Pass Rate by Mode (Judge v1)

| Mode | N | Assertion Pass | Judge Pass | Both Pass | Rate |
|------|---|----------------|------------|-----------|------|
| notes-summarisation | 6 | 6/6 | 4/6 | 4/6 | 66.7% |
| exclusion-citation | 9 | 8/9 | 9/9 | 8/9 | 88.9% |
| coverage-confirmation | 5 | 5/5 | 5/5 | 5/5 | 100.0% |
| excess-deductible | 3 | 3/3 | 3/3 | 3/3 | 100.0% |
| regression | 2 | 2/2 | 2/2 | 2/2 | 100.0% |
| **TOTAL** | 25 | 24/25 | 23/25 | 22/25 | 88.0% |

---

## Human Blind Labels (labels_25.json)

| ID | Mode | Human Label | Notes |
|---|---|---|---|
| 1 | notes-summarisation | PASS | Burst supply line, coverage confirmed, $1,500 deductible — all supported by note |
| 2 | exclusion-citation | FAIL | Summary says 'Date of Loss: Unknown' — notes do not state a date, but summary in |
| 3 | excess-deductible | PASS | Named Storm deductible computed correctly ($7,000 > $5,000). Coverage A $350,000 |
| 4 | coverage-confirmation | PASS | Mold remediation covered, HO-0306 MF-2, $1,000 deductible. All facts traceable t |
| 5 | exclusion-citation | PASS | Mold from humidity, E-22 exclusion cited, denial confirmed. Notes mention 'Date  |
| 6 | exclusion-citation | PASS | Air quality testing denied per MF-3, $1,200 deductible mentioned for remediation |
| 7 | exclusion-citation | PASS | Earthquake excluded under CLAUSE EM-1, E-31, denial confirmed. Notes say 'no ded |
| 8 | exclusion-citation | PASS | Sinkhole, E-33, denial. Summary accurate and faithful. |
| 9 | exclusion-citation | PASS | Concurrent causation CLAUSE EM-2, E-31, denial. Summary accurately reflects note |
| 10 | exclusion-citation | PASS | Business pursuits E-19, HO-0309. Denial correct. Date shows N/A — notes say '20  |
| 11 | notes-summarisation | FAIL | Summary says 'Exclusion(s) Cited: E-19, BP-3' but notes describe CLAUSE BP-3 as  |
| 12 | coverage-confirmation | PASS | Scheduled jewelry, mysterious disappearance covered, $2,500 deductible. Summary  |
| 13 | coverage-confirmation | FAIL | Summary says 'Policy Form: HO-0304 ed 03-24 E-17' — this incorrectly formats E-1 |
| 14 | excess-deductible | PASS | Named Storm Brenda-2025, $5,600 deductible (2% of $280,000 = $5,600 > $5,000), a |
| 15 | notes-summarisation | PASS | Washing machine hose, sudden and accidental, CLAUSE WD-1, 14-day limit cited cor |
| 16 | notes-summarisation | PASS | Mold remediation covered, air quality testing denied under MF-3, $2,000 deductib |
| 17 | exclusion-citation | PASS | Land subsidence, E-34, HO-0308, denial. Summary slightly miswords 'exclusion E-3 |
| 18 | exclusion-citation | PASS | Airbnb, E-36 and E-19, denial. Both exclusion codes in notes. Faithful. |
| 19 | coverage-confirmation | FAIL | Summary says 'per exclusion code E-17' — notes say E-17 CONFIRMS coverage, it is |
| 20 | notes-summarisation | PASS | Unscheduled necklace, E-28, HO-0307, denial. All facts from notes. Faithful. |
| 21 | notes-summarisation | PASS | Freelance designer, E-19, business pursuits, denial. Summary faithful to notes. |
| 22 | excess-deductible | PASS | Clara-2025, $8,400 deductible (2% of $420,000), $31,000 damage, coverage confirm |
| 23 | coverage-confirmation | PASS | Hot water heater PRV, sudden and accidental, HO-0304, $1,000 deductible. All fro |
| 24 | regression | PASS | Regression case. Summary correctly states E-17 confirms coverage NOT withheld. N |
| 25 | regression | PASS | Regression case. Summary correctly states E-18 does not appear in HO-0304, table |

---

## Agreement Before → After

| Version | Agreement | Matches | Total |
|---------|-----------|---------|-------|
| Judge v1 (before) | **76.0%** | 19 | 25 |
| Judge v2 (after)  | **84.0%** | 21 | 25 |

**agreement_before = 76.0%**  
**agreement_after  = 84.0%**

---

## Prediction (Written Before Judge Iteration)

```
PREDICTION (written 2026-09-10, before judge v2 iteration)
==========================================================

The judge v1 fails on cases where the summary faithfully paraphrases or
reformats adjuster notes (e.g., citing a policy clause as part of a form
name, or referencing E-17 as an "exclusion code" when it is a coverage
confirmation) — I predict that adding two few-shot examples showing these
borderline-accurate summaries labelled PASS will reduce false-FAIL verdicts
and move agreement from roughly 75-80% up to 88-92%.

WHERE I EXPECT TO BE WRONG: The judge may still struggle with cases where the
summary uses an exclusion code in an atypical context (E-17 as coverage
confirmation rather than denial), because the few-shot examples cannot cover
every reformatting pattern — those edge cases may stay misclassified in v2.
```

---

## Disagreement Analysis (Judge v1)

**Total disagreements (v1): 6**

### Disagreement 1 — Case 01

**Mode:** notes-summarisation  
**Human label:** PASS  
**Judge v1 verdict:** FAIL  
**Judge reason:** The summary adds a coverage decision (“COVERED”) that is not stated in the adjuster notes.  

**Adjuster notes (first 300 chars):**  
```
Insured reports burst supply line under kitchen sink on 15 Mar 2024. Water damage confined to kitchen cabinet base and vinyl flooring approx 12 sq ft. Plumber confirmed sudden failure of braided steel supply line, no evidence of prior leakage. Repair estimate $3,200. Deductible $1,500. Policy form H...
```

**Verdict: HUMAN was right.** The judge false-failed a faithful summary — the claim the judge flagged as invented IS supported by the adjuster notes.

---

### Disagreement 2 — Case 02

**Mode:** exclusion-citation  
**Human label:** FAIL  
**Judge v1 verdict:** PASS  
**Judge reason:** The summary accurately reflects all facts stated in the adjuster notes.  

**Adjuster notes (first 300 chars):**  
```
Insured reports water staining on ceiling, estimated 6 months of slow drip from dishwasher supply hose. Continuous seepage confirmed, duration exceeds 14 consecutive days per CLAUSE WD-1 of HO-0304 ed 03-24. Exclusion E-11 applies. Claim denied. Deductible would have been $2,000....
```

**Verdict: HUMAN was right.** The judge missed an invented claim. The summary added information not present in the adjuster notes.

---


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
