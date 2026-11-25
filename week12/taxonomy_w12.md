# Week 12 Error Taxonomy — Insurance Claims Triage Agent

**Scope:** Integrated W12 system (RAG + MCP tools + trajectory eval).  
**Sample:** 10 trajectory traces (Week 8 results) + 5 flood-straddle cases added in W12.  
**Last updated:** 2026-11-11

---

## Error Modes

### 1. `excess_steps`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 25% of traced claims |
| **Severity**   | LOW — inefficiency only; correct outcome produced |
| **Impact**     | Annoys adjuster; inflates cost per claim (~1.4x token spend) |
| **Inherited**  | ✅ INHERITED from Week 8 trajectory eval |

**Description:** Agent calls more tools than the optimal path requires — e.g., calling `search_policy_exclusions` on a clear pipe-burst case that has no applicable exclusion, or calling `get_claim` twice. No wrong output is produced, but latency and token cost increase.

**Example trace:** `e1a2b3c4-0000-4000-8000-000000000001`

**Fix path:** Prune tool call prompt; add "skip exclusion search if no exclusion keyword in notes" heuristic.

---

### 2. `wrong_tool_order`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 15% of traced claims |
| **Severity**   | MEDIUM — may surface wrong policy version before date filter runs |
| **Impact**     | Adjuster receives summary citing policy retrieved before date-check context was set |
| **Inherited**  | ✅ INHERITED from Week 8 trajectory eval |

**Description:** Agent calls `search_policy_exclusions` before `check_coverage_in_force`, meaning the RAG retrieval runs without the endorsement-year date filter. The wrong policy version may be fetched and cited in the summary even if `check_coverage_in_force` later corrects it — the summary may already be half-written with wrong wording.

**Example trace:** `f4d5e6a7-1111-4111-9111-111111111111`

**Fix path:** Enforce tool ordering in system prompt: `get_claim → check_coverage_in_force → (optional) search_policy_exclusions → refer_to_adjuster`.

---

### 3. `skip_exclusions`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 20% of traced claims |
| **Severity**   | HIGH — wrongly pays (agent omits exclusion check that would have blocked payout) |
| **Impact**     | Claim proceeds to adjuster without exclusion flag; adjuster may pay without noting E-NN |
| **Inherited**  | ✅ INHERITED from Week 8 trajectory eval |

**Description:** Agent skips `search_policy_exclusions` on cases where an exclusion does apply — most commonly seepage cases (E-11) and mold-from-humidity cases (E-22). Without the exclusion search, the summary omits the E-NN code, and the case looks like a standard covered loss.

**Example trace:** `a9c8d7f6-2222-4222-b222-222222222222`

**Fix path:** Add mandatory `search_policy_exclusions` trigger when adjuster notes contain keywords: *seepage*, *mold*, *gradual*, *continuous*.

---

### 4. `wrong_endorsement_version` 🆕

| Field       | Value |
|-------------|-------|
| **Frequency**  | 15% of traced claims (60% of flood-straddle cases before fix) |
| **Severity**   | HIGH — wrongly denies **or** wrongly pays against incorrect policy wording |
| **Impact**     | For a 2024-12-31 flood loss: system retrieves FL-3A (2025 wording) because it ranks highest in vector search; 2023 wording (FL-3) governs. Payout limits differ. |
| **Inherited**  | ❌ **NEW — created by integration** (see §Integration-Created Mode below) |
| **Trace**      | `a3f9b2c1-4e77-4b8d-9c21-6f8d2a1b3c05` |

**Description:** When a loss date straddles an endorsement renewal boundary (e.g., 2024-12-31 vs 2025-01-01), the RAG retriever without a date filter returns the most semantically similar clause — which is the **latest** endorsement (2025 FL-3A). The 2023 endorsement (FL-3) governs losses on or before 2024-12-31. This mode did not exist in standalone components because the RAG and the coverage checker were never wired together until Week 12.

**Before W12 fix:** 3 out of 5 flood-straddle cases retrieved wrong endorsement.  
**After W12 fix:** 0 out of 5 — date filter wired into `check_coverage_in_force → RAG` path.

**Fix path:** Pass `endorsement_year` from `check_coverage_in_force` result as a metadata filter to `search_policy_exclusions` before vector retrieval.

---

### 5. `deductible_sublimit_confusion`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 10% of traced claims |
| **Severity**   | MEDIUM — annoys adjuster; may cause wrong payout if adjuster trusts summary |
| **Impact**     | Summary conflates deductible with sublimit, or omits policy limit entirely |
| **Inherited**  | ✅ INHERITED (latent in W6 summaries; surfaced by W12 three-amounts assertion) |
| **Trace**      | `b7e3d4f2-5a88-4c99-aa33-3b2e1d4c5f06` |

**Description:** Agent produces a summary mentioning only one or two of the three distinct financial constraints (deductible, sublimit, policy limit), or uses the terms interchangeably. For example: "Deductible of $2,500 applies (capped at $50,000)." — this conflates the deductible with the flood sublimit.

**Fix path:** Structured output schema requiring three separate fields: `deductible`, `sublimit`, `policy_limit`.

---

### 6. `coverage_decision_leaked`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 10% of traced claims |
| **Severity**   | HIGH — compliance violation; automated system usurped adjuster role |
| **Impact**     | Regulatory and E&O liability; claim may be prematurely paid or denied |
| **Inherited**  | ✅ INHERITED (W6 judge sometimes flagged but never hard-blocked) |
| **Trace**      | `c5a1e9b8-6b77-4d00-bc44-4c3f2e5d6a07` |

**Description:** Summary contains a final coverage verdict phrase such as *"the claim is covered"*, *"claim is denied"*, *"coverage confirmed"*, or *"claim approved"*. The W12 system is designed to triage and refer — not decide. Any such phrase is a compliance violation.

**W12 assertion:** `check_no_coverage_decision(text)` — hard fail if any banned phrase found.

**Fix path:** Add forbidden-phrase list to system prompt; use regex post-filter before returning summary.

---

### 7. `pii_in_output`

| Field       | Value |
|-------------|-------|
| **Frequency**  | 5% of traced claims |
| **Severity**   | HIGH — compliance/regulatory (CCPA, state insurance data privacy rules) |
| **Impact**     | Claimant names, addresses, DOB, phone numbers may appear verbatim in triage output seen by downstream systems |
| **Inherited**  | ✅ INHERITED (adjuster_notes passed through verbatim in W6–W11) |
| **Trace**      | `d2f7c3a4-7c66-4e11-cd55-5d4a3f6e7b08` |

**Description:** When `get_claim` or `get_adjuster_notes` returns raw adjuster notes, claimant PII (full name, street address, phone, DOB) is embedded. Without a redaction pass, this PII propagates into the LLM context and may appear in generated summaries.

**W12 fix:** `redact()` applied to `adjuster_notes` before passing to LLM. Covers: full-name pairs, street addresses (regex), phone patterns, DOB patterns.

**Remaining gap:** Single-name claimants ("Dr. Smith"), non-Western names, compound names ("John-Mary"). See `weaknesses.md`.

---

## Integration-Created Mode

> **`wrong_endorsement_version` did not exist as a failure mode in any standalone component prior to Week 12.**

- In isolation: the RAG retriever returns the most relevant clause regardless of date — acceptable when there is only one endorsement version.
- In isolation: `check_coverage_in_force` correctly identifies the governing endorsement year from policy metadata — but it does not pass that year downstream to the retriever.
- **At integration:** these two components were wired together for the first time. The RAG retriever continued to rank by semantic similarity without date context, overriding the endorsement-year signal from `check_coverage_in_force`.

This is a classic **seam defect**: each component correct in isolation; the interface between them introduced the bug.

The W12 eval suite specifically targets this seam with 5 flood-straddle cases and the `check_endorsement_version_cited` assertion.

---

## Summary Table

| # | Mode | Frequency | Severity | New/Inherited |
|---|------|-----------|----------|---------------|
| 1 | `excess_steps` | 25% | LOW | Inherited |
| 2 | `wrong_tool_order` | 15% | MEDIUM | Inherited |
| 3 | `skip_exclusions` | 20% | HIGH | Inherited |
| 4 | `wrong_endorsement_version` | 15% | HIGH | **NEW** |
| 5 | `deductible_sublimit_confusion` | 10% | MEDIUM | Inherited |
| 6 | `coverage_decision_leaked` | 10% | HIGH | Inherited |
| 7 | `pii_in_output` | 5% | HIGH | Inherited |

> Frequencies sum to 100%. A single claim trace may exhibit more than one mode simultaneously (e.g., `wrong_tool_order` often co-occurs with `wrong_endorsement_version`).
