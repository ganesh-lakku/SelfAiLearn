# Week 12 Integration Seam List

**Date:** Tuesday 2026-11-11 (unedited seam list from integration session)  
**System:** Insurance Claims Triage Agent — W12 integrated build  
**Seams reviewed:** 10  

---

## Seam Status Legend

| Status | Meaning |
|--------|---------|
| ✅ **FIXED** | Seam defect identified and resolved in W12 |
| 🟡 **ACCEPTED** | Known gap; above minimum gate; accepted for demo |
| ⏰ **ran-out-of-time** | Not resolved; uses mock/stub; flagged for Week 13 |

---

## Seam List

### 1. RAG retrieval → W12 agent (date filter wiring)
**Status: ✅ FIXED**

**Seam:** `check_coverage_in_force` returns `endorsement_year` in its result object, but the RAG retrieval call in `search_policy_exclusions` did not read that field — it ran a plain vector search with no metadata filter.

**Fix:** Added `endorsement_year` as a ChromaDB `where` filter in `search_policy_exclusions`. When `endorsement_year="2023"` is passed, the retriever filters to documents tagged `{"endorsement": "2023"}` before ranking by cosine similarity.

**Before:** 3/5 flood-straddle cases retrieved wrong endorsement.  
**After:** 0/5.

---

### 2. `mcp_server_policy.py` → `check_coverage_in_force` tool
**Status: ✅ FIXED**

**Seam:** `check_coverage_in_force` was registered in the MCP server but its `loss_date` parameter schema used `format: date-time` (ISO 8601 with time), while the agent was passing bare dates (`"2024-12-31"`). The MCP server rejected calls with a schema validation error.

**Fix:** Changed parameter schema to `format: date` (date only). Added coercion for datetime strings: if time component present, truncate to date.

---

### 3. `mcp_server_policy.py` → `refer_to_adjuster` tool
**Status: ✅ FIXED**

**Seam:** `refer_to_adjuster` accepted a free-text `reason` field but did not validate that the reason was non-empty, and did not block downstream calls after referral. Agent occasionally called `compute_payout` after `refer_to_adjuster` (tool order violation).

**Fix:** Added `reason` required validation (min 10 chars). Added a session-level `referred` flag: once set, `compute_payout` returns an error `"Referral already issued — payout computation blocked."`

---

### 4. `tracer.py` → span trace across MCP hop
**Status: ✅ FIXED**

**Seam:** When the agent called an MCP tool, the OpenTelemetry span context was not propagated across the subprocess boundary. Tool spans appeared as root spans in Jaeger — no parent link to the agent's main trace.

**Fix:** Added `traceparent` header injection into MCP tool call metadata. MCP server now reads `traceparent` from call metadata and creates child spans. Traces now show the full: `agent_turn → get_claim → check_coverage_in_force → search_policy_exclusions → refer_to_adjuster` chain.

---

### 5. `eval_suite_w12.py` → judge agreement on endorsement-version assertion
**Status: 🟡 ACCEPTED**

**Seam:** The `check_endorsement_version_cited` assertion requires the output to contain both a clause ID (e.g., `FL-3`) AND the endorsement year (e.g., `2023`) in a citation context. The LLM judge sometimes accepts `"2023 wording"` as sufficient even without a clause ID — partial match.

**Measured agreement rate:** 87% (gate: ≥85%).  
**Gap source:** 2 false-positive disagreements in the 35-case suite where judge passes but assertion fails (clause ID absent).

**Decision:** Accepted at 87% — above 85% gate, below 90% ideal. Flagged for hardening in Week 13 (require clause ID in judge rubric).

---

### 6. PII redaction of adjuster notes
**Status: ✅ FIXED**

**Seam:** `get_claim` and `get_adjuster_notes` MCP tools returned `adjuster_notes` verbatim, including claimant full names, addresses, DOB, and phone numbers. A partner squad's agent that called our MCP server on Thursday received un-redacted notes.

**Fix:** Added `redact(text)` post-processor in both tool handlers:
- Regex: `r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"` → `"[REDACTED NAME]"` (proper-name pairs)
- Regex: `r"\b\d{3,5}\s+\w+\s+(Street|St|...)\b"` → `"[REDACTED ADDRESS]"`
- Regex: `r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"` → `"[REDACTED PHONE]"`
- Regex: `r"\b\d{4}-\d{2}-\d{2}\b"` (after claim date removed) → `"[REDACTED DOB]"`

**Known gap:** Single-name claimants, non-Western names, compound names. See `weaknesses.md`.

---

### 7. Deductible / sublimit / policy-limit three-way split in claim data
**Status: ✅ FIXED**

**Seam:** Claim data model had a single `excess_amount` field. Sublimit and policy limit were buried in `adjuster_notes` as free text. The agent had no structured access to these values and sometimes conflated them.

**Fix:** Added `flood_sublimit` and `policy_limit` as top-level fields in the claim schema (MCP server `get_claim` response). Updated prompt template to format all three as a labeled list. Added W12 assertion `check_three_amounts_distinct`.

---

### 8. Flood-straddle bonus eval (5 cases before→after)
**Status: ✅ FIXED**

**Seam:** No eval cases existed that specifically targeted the endorsement-year boundary. The existing 25 W6 cases used loss dates in 2024 Q1–Q3, well inside the 2023 endorsement window.

**Fix:** Added 5 flood-straddle cases (IDs 26–30) covering 2024-12-29, 2024-12-30, 2024-12-31, 2025-01-01, 2025-01-02. The eval suite reports `wrong_endorsement_before` (3) vs `wrong_endorsement_after` (0).

Regression guard: CLM-2024-77202 (2024-12-31) is marked `is_regression: true` — any future change that causes wrong endorsement for this case fails the CI gate.

---

### 9. MCP server tool discovery at runtime (not hardcoded)
**Status: ✅ FIXED** (existing from Week 7)

**Seam:** Early builds hardcoded the available tool list in the agent system prompt. Adding a new MCP tool required prompt edits.

**Fix** *(Week 7, carried forward):* Agent calls `tools/list` at startup and builds its available-tools context dynamically. W12 inherited this — no regression.

---

### 10. Week 8 trajectory eval rewired to W12 agent
**Status: ⏰ ran-out-of-time**

**Seam:** `trajectory_w12.py` is intended to replay actual W12 agent runs and compare tool sequences to expected sequences. The W12 agent (`w12_agent.run_w12_agent`) was not completed in time to instrument live tool-call traces during the eval window.

**Current state:** `trajectory_w12.py` uses `MOCK_ACTUAL_SEQUENCES` — a hand-coded dict of realistic (but not live-captured) tool sequences. The accuracy figures (73% overall, 100% flood-straddle) reflect the expected post-fix behavior, not live observation.

**Risk:** If the live agent deviates from mock sequences, the trajectory accuracy figure is wrong. At hailstorm volume, this means wrong-path estimates for SLA analysis may be understated.

**Plan for Week 13:** Wire `tracer.py` span export → `trajectory_w12.py` loader. Replace `MOCK_ACTUAL_SEQUENCES` with `load_from_traces(traces_path)`.

---

## Summary

| # | Seam | Status |
|---|------|--------|
| 1 | RAG retrieval → W12 agent (date filter wiring) | ✅ FIXED |
| 2 | `mcp_server_policy.py` → `check_coverage_in_force` | ✅ FIXED |
| 3 | `mcp_server_policy.py` → `refer_to_adjuster` | ✅ FIXED |
| 4 | `tracer.py` → span trace across MCP hop | ✅ FIXED |
| 5 | eval judge agreement on endorsement-version assertion | 🟡 ACCEPTED (87%) |
| 6 | PII redaction of adjuster notes | ✅ FIXED |
| 7 | Deductible/sublimit/policy-limit three-way split | ✅ FIXED |
| 8 | Flood-straddle bonus eval (5 cases before→after) | ✅ FIXED |
| 9 | MCP tool discovery at runtime | ✅ FIXED (Week 7) |
| 10 | Week 8 trajectory eval rewired to W12 agent | ⏰ ran-out-of-time |
