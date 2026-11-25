# Week 12 — 10-Minute Demo Script (The Four-Part Standard)

**Variant D:** Claims Triage & Coverage Assistant  
**Clock Limit:** Exactly 10:00 minutes. No slides, terminal + code only.

---

## Part 1: A Real Run (0:00 – 3:00)

**Speaker Action:**
Run the master command with claim `CLM-2024-77202`:
```bash
python3 week12/run_week12.py --claim-id CLM-2024-77202
```

**Talking Points & Terminal Highlights:**
1. **The Claim:** Point out loss date: `2024-12-31` — literally the final day of the 2023 endorsement set, one day before the 2025 flood rewrite took effect.
2. **Hop 1 — `get_claim`:** Agent reads the FNOL. Point to the MCP call logged with sanitized adjuster notes.
3. **Hop 2 — `check_coverage_in_force`:** Highlight the visible MCP tool call:
   ```json
   check_coverage_in_force(policy_number="POL-HO-772202", loss_date="2024-12-31")
   --> in_force: true, endorsement_set: "2023", clause: "FL-3"
   ```
4. **Three Distinct Numbers:** Show terminal output clearly reporting:
   - **Deductible:** `$2,500.00`
   - **Flood Sub-Limit:** `$50,000.00`
   - **Policy Limit:** `$400,000.00`
   *State out loud:* "Juniors confuse deductible and sub-limit weekly. Notice our system isolates all three figures into discrete schema fields."
5. **Hop 3 — `refer_to_adjuster`:** Point to the final tool invocation:
   - Action: `REFER_TO_ADJUSTER`
   - Citation: `[CLAUSE FL-3 | ENDORSEMENT 2023 | LOSS DATE 2024-12-31]`
   - Verify: System *never* stated "claim is covered" or "claim is denied". It surfaced the threshold evidence and referred to a human adjuster.

---

## Part 2: The Failures We Found (3:00 – 5:30)

**Speaker Action:**
Open `week12/taxonomy_w12.md` and display trace `a3f9b2c1-4e77-4b8d-9c21-6f8d2a1b3c05`:
```bash
grep -n -C 5 "a3f9b2c1" week12/taxonomy_w12.md
```

**Talking Points:**
1. **The Live Wound Recreated:** "Here is the trace where an August 2024 flood claim was evaluated against the 2025 flood exclusion wording. Why did it happen? Because the 2025 wording (`FL-3A`) had stronger embedding similarity for 'surface water ingress' than the 2023 clause (`FL-3`). The vector retriever preferred the newer document simply because it was phrased better."
2. **The Integration-Created Failure Mode:** Show mode `wrong_endorsement_version` in the taxonomy (15% baseline frequency). Explain:
   - "This failure mode did *not* exist when Week 3 RAG or Week 7 agent ran in isolation. It was created purely by integration: when we wired the agent to a multi-version policy corpus, vector ranking trumped temporal law."
3. **The Two Unprompted Weaknesses (from Wednesday):**
   - *Weakness 1:* Day-level granularity vs. midnight storm timestamps.
   - *Weakness 2:* Heuristic PII scrubbing vs. single-token contractor names in free-text notes.

---

## Part 3: A Number That Moved (5:30 – 8:00)

**Speaker Action:**
Run the evaluation suite comparison:
```bash
python3 week12/eval_suite_w12.py
```

**Talking Points & Terminal Highlights:**
1. **The Metric That Moved:**
   - **Wrong Endorsement Citation Rate:**
     - **Before Date Filter:** **60.0%** (3 out of 5 flood-straddle cases cited the 2025 wording for a 2024 loss).
     - **After Code-Enforced Date Filter:** **0.0%** (0 out of 5 errors; 5/5 green).
     - *Sample Size:* $n=5$ boundary-straddling claims spanning 2024-08-15 to 2025-01-01.
2. **Judge Agreement Number:**
   - Deterministic assertions run first on 35 cases.
   - LLM judge validation agreement on integrated outputs: **87.1%** (clears the 85% requirement).
3. **What The Suite Does NOT Measure (The Honest Caveat):**
   *Read verbatim:* "Our eval suite does NOT measure multi-policy concurrent causation disputes where an uninsured wind peril acts concurrently with an excluded flood peril under conflicting endorsement years."

---

## Part 4: What's Next & The 10× Plan (8:00 – 10:00)

**Speaker Action:**
Show `week12/cost_tenx.md` and the regression guard case:

**Talking Points:**
1. **Closed Failure-to-Test Loop:**
   - Case `CLM-2024-77202` (2024-12-31 loss) is now permanently added to `week12/eval_suite_w12.py` as an automated regression guard. If any developer removes the date filter, CI goes red instantly.
2. **Cost per Claim Triaged:**
   - **$0.00048** per triage run (~820 tokens total).
   - Local embeddings and ChromaDB cost $0.00.
3. **What Breaks First at 10× Volume (18,000 FNOLs Hailstorm Week):**
   - "Not cost ($8.64 for the entire week). Not local vector compute (<5 QPS)."
   - "The first thing that breaks is **Groq Tier 1 Rate Limits (30 RPM / 6,000 TPM)**. In the first hour of a hailstorm, 300 claims arrive per minute — exceeding the provider quota by **1,000%**. It will throw HTTP 429 and blow p99 latency to 45 seconds."
   - "The fix: Redis queue dispatcher paired with persistent FastMCP worker daemons."

---
*End of demo — exactly at 10:00.*

