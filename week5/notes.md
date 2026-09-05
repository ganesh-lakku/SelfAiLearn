# Week 5 — Notes (Open-Coding + Evidence)

**Date:** 2026-09-05  
**Domain:** Insurance Claims — Homeowners Endorsements  

## PII Redaction Confirmation

> Claimant names and claim numbers are redacted **before** the trace is written to `traces.jsonl`, not after. The `redact()` function in `src/tracer.py` strips `CLM-YYYY-NNNNN` patterns and proper-name pairs from the question string at write time. No raw claimant identifier ever reaches disk.

## Seeded Random Sample

- **Random seed:** `42`
- **Total traces in corpus:** 40
- **Sample size:** 20

| # | trace_id | refusal? | question (first 80 chars) |
|---|----------|----------|---------------------------|
| 1 | `f3593ac6-6b44-48cf-8c63-b93f79d37c4e` | YES | Does exclusion E-18 appear in HO-0304? |
| 2 | `d0ea10da-b22c-428f-bd64-20c80bbea64f` | no | What does sudden and accidental mean under CLAUSE WD-1 in HO-0304? |
| 3 | `00759229-8fad-41da-9e70-51c509c2d070` | YES | Under HO-0306, is the policyholder required to mitigate mold growth? |
| 4 | `a5a423a8-cfde-4ae3-ac4e-ec6e4ed03ff5` | no | What does HO-0306 say about fungi that grow on wood framing? |
| 5 | `a52a3f6a-66c0-4b4a-bfaa-eba211063066` | no | Is there a sublimit for mold remediation under HO-0306? |
| 6 | `e72c7899-3e15-49c9-97a8-8a862518b382` | no | What is the Named Storm deductible amount under HO-0305 ed. 03-24? |
| 7 | `eac786c4-b6e3-482c-af2f-6e9476746bde` | no | What exclusions apply to water damage under HO-0304? |
| 8 | `b3ffd6f1-4766-43bb-88e5-d42789a5f6eb` | no | Does HO-0304 cover damage from a slowly dripping appliance hose? |
| 9 | `54cd6070-8fa5-4511-8d46-51f05605e841` | YES | What is exclusion E-32 in HO-0308? |
| 10 | `6c668224-9908-411b-a399-b635a47ab7c5` | YES | What is the underwriting guideline for coastal flood zone AE maximum insured val |
| 11 | `834c39c2-a0a8-4b82-9925-d760f9e045fc` | YES | Does exclusion E-17 apply under form HO-0304 ed. 03-24, and is a burst supply li |
| 12 | `173988e5-a8ba-4756-8c5a-06c821275dd6` | no | What is a supply line as defined in HO-0304 CLAUSE WD-2? |
| 13 | `722e6982-f4bb-4982-a7bf-5d2bbaa11237` | YES | What is exclusion E-36 in HO-0309? |
| 14 | `df85bab6-e848-45eb-898e-b18a1fb4ce04` | YES | Has subrogation been pursued on the supply-line claim from March 2024? |
| 15 | `aa6c9c68-6eb1-4579-8eeb-ebaaa4e5cc1e` | no | Does HO-0306 exclude mold that results from long-term humidity? |
| 16 | `d923fc89-4747-4084-8b50-26625d18daea` | YES | What property must be scheduled under HO-0307 to receive coverage? |
| 17 | `1d67132f-5d28-4d60-a7a5-7220c2259d7c` | no | Does exclusion E-19 appear in HO-0309 ed. 05-24 for business pursuits? |
| 18 | `f6a83ee4-afe3-4edb-b783-5628a0e08e15` | YES | What is the reserve amount for the earth-movement claim filed last quarter? |
| 19 | `a4aeddb6-b266-4dad-96c9-520f212e234a` | YES | Is freelance consulting work excluded under HO-0309? |
| 20 | `047a227c-8927-4677-8bf5-cdcbaa894e61` | YES | Is there a per-item limit under HO-0307 for unscheduled items? |

## Replay Evidence

**Trace replayed:** `468ce19a-602f-454d-b492-3cfb124569cd`  
**Replay seed used:** `99`  
**Prompt version:** `v1.0.0-week5`  
**Model:** `openai/gpt-oss-120b`  
**Model params:** `{'temperature': 0.0, 'max_tokens': 800}`  
**Chunks retrieved:** `HO-0308_sa_chunk_004`, `HO-0308_sa_chunk_007`, `HO-0308_sa_chunk_008`, `HO-0308_sa_chunk_003`, `HO-0308_sa_chunk_002`  

### Required Field Audit

| Field | Present? |
|-------|----------|
| `trace_id` | ✅ |
| `timestamp` | ✅ |
| `prompt_version` | ✅ |
| `question` | ✅ |
| `retrieved_chunks` | ✅ |
| `model` | ✅ |
| `model_params` | ✅ |
| `raw_output` | ✅ |
| `is_refusal` | ✅ |

> All required fields present — fully replayable.

### Original Output

```
Yes. HO‑0308 incorporates a concurrent‑causation rule for earth‑movement losses. CLAUSE EM‑2 states that when earth movement and a covered peril act together, the loss is excluded and coverage does not attach to any portion attributable to the covered peril [ SOURCE: HO-0308_sa_chunk_004 | HO-0308 | CLAUSE-EM-2 ]. The exclusion table also notes that the “Concurrent cause rule applies (CLAUSE EM‑2)” for the earth‑movement exclusion [ SOURCE: HO-0308_sa_chunk_007 | HO-0308 | EXCLUSION-TABLE ].
```

### Replayed Output

```
Yes. HO‑0308 contains a “Concurrent Causation Rule” that states if earth movement and a covered peril act together (concurrently or in sequence) to cause a loss, the entire loss is excluded under the endorsement [ SOURCE: HO-0308_sa_chunk_004 | HO-0308 | CLAUSE-EM-2 ]. This rule is also referenced in the ensuing‑loss exception note, which notes that water damage from ruptured pipes caused by earth movement is excluded under the concurrent‑cause rule of CLAUSE EM‑2 [ SOURCE: HO-0308_sa_chunk_008 | HO-0308 | CLAUSE-EM-3 ].
```

## Open-Coding — 20 Observation Sentences

> **Rule:** One honest sentence per trace describing what was SEEN. No category labels, no diagnoses, no fixes. 'I don't know why this failed' is a permitted sentence.

> ⚠️  Zero code changes were made during this open-coding step.

### Trace 01: `f3593ac6-6b44-48cf-8c63-b93f79d37c4e`

**Question:** Does exclusion E-18 appear in HO-0304?  
**is_refusal:** True  
**Top retrieval score:** 0.6546  
**Forms in top-5:** HO-0305, HO-0306, HO-0309, HO-0308, HO-0307  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. exclusion E-18 in HO-0304) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 02: `d0ea10da-b22c-428f-bd64-20c80bbea64f`

**Question:** What does sudden and accidental mean under CLAUSE WD-1 in HO-0304?  
**is_refusal:** False  
**Top retrieval score:** 0.7318  
**Forms in top-5:** HO-0308, HO-0306, HO-0307, HO-0304  
**Output (first 300 chars):** `Under CLAUSE WD‑1 in form HO‑0304, “sudden and accidental” is defined as an event that is **abrupt, unintended, and not the result of continuous seepage or leakage lasting more than fourteen (14) consecutive days**. [SOURCE: HO-0304_sa_chunk_003 | HO-0304 | CLAUSE-WD-1]`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 03: `00759229-8fad-41da-9e70-51c509c2d070`

**Question:** Under HO-0306, is the policyholder required to mitigate mold growth?  
**is_refusal:** True  
**Top retrieval score:** 0.6182  
**Forms in top-5:** HO-0306  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. policyholder mitigation requirement) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 04: `a5a423a8-cfde-4ae3-ac4e-ec6e4ed03ff5`

**Question:** What does HO-0306 say about fungi that grow on wood framing?  
**is_refusal:** False  
**Top retrieval score:** 0.4281  
**Forms in top-5:** HO-0306  
**Output (first 300 chars):** `HO‑0306 expressly excludes any loss caused by fungi. The endorsement states that loss “caused directly or indirectly by … fungi” is not covered, and the exclusion applies regardless of the source of the fungi [ SOURCE: HO-0306_sa_chunk_003 | HO-0306 | CLAUSE-MF-1 ]. The exclusion table reinforces th`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 05: `a52a3f6a-66c0-4b4a-bfaa-eba211063066`

**Question:** Is there a sublimit for mold remediation under HO-0306?  
**is_refusal:** False  
**Top retrieval score:** 0.5804  
**Forms in top-5:** HO-0306  
**Output (first 300 chars):** `Yes. Under HO‑0306 there is a specific sublimit for mold remediation: the endorsement will pay up to **$10,000** for mold remediation costs when the required conditions are met【SOURCE: HO-0306_sa_chunk_005 | HO-0306 | CLAUSE-WD-1】. Additionally, the endorsement includes a “remediation sublimit excep`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 06: `e72c7899-3e15-49c9-97a8-8a862518b382`

**Question:** What is the Named Storm deductible amount under HO-0305 ed. 03-24?  
**is_refusal:** False  
**Top retrieval score:** 0.7269  
**Forms in top-5:** HO-0305  
**Output (first 300 chars):** `The Named Storm deductible is **$5,000 or 2 % of the Coverage A limit, whichever is greater**. For example, a dwelling with $300,000 coverage would have a $6,000 deductible (2 % of $300,000), while a dwelling with $200,000 coverage would have the minimum $5,000 deductible because the floor applies. `  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 07: `eac786c4-b6e3-482c-af2f-6e9476746bde`

**Question:** What exclusions apply to water damage under HO-0304?  
**is_refusal:** False  
**Top retrieval score:** 0.5906  
**Forms in top-5:** HO-0308, HO-0304  
**Output (first 300 chars):** `The HO‑0304 endorsement contains the following specific exclusions for water‑damage losses:

* **E‑11 – Gradual seepage or leakage** – any water that seeps, leaks, or flows continuously for more than 14 days. [ SOURCE: HO-0304_sa_chunk_006 | HO-0304 | EXCLUSION‑TABLE ]

* **E‑12 – Flood from externa`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 08: `b3ffd6f1-4766-43bb-88e5-d42789a5f6eb`

**Question:** Does HO-0304 cover damage from a slowly dripping appliance hose?  
**is_refusal:** False  
**Top retrieval score:** 0.4570  
**Forms in top-5:** HO-0308, HO-0304  
**Output (first 300 chars):** `No. HO‑0304 only covers “sudden and accidental” discharge or overflow from plumbing, heating, air‑conditioning, sprinkler systems, or household appliances, and defines “sudden and accidental” as an event that is abrupt, unintended, and **not** the result of continuous seepage or leakage lasting more`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 09: `54cd6070-8fa5-4511-8d46-51f05605e841`

**Question:** What is exclusion E-32 in HO-0308?  
**is_refusal:** True  
**Top retrieval score:** 0.6485  
**Forms in top-5:** HO-0305, HO-0306, HO-0309, HO-0308, HO-0307  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. exclusion E-32 in HO-0308) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 10: `6c668224-9908-411b-a399-b635a47ab7c5`

**Question:** What is the underwriting guideline for coastal flood zone AE maximum insured value?  
**is_refusal:** True  
**Top retrieval score:** 0.5418  
**Forms in top-5:** HO-0305, HO-0304  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. coastal flood zone AE maximum insured value) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 11: `834c39c2-a0a8-4b82-9925-d760f9e045fc`

**Question:** Does exclusion E-17 apply under form HO-0304 ed. 03-24, and is a burst supply line covered?  
**is_refusal:** True  
**Top retrieval score:** 0.5293  
**Forms in top-5:** HO-0305, HO-0306, HO-0309, HO-0308, HO-0307  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. exclusion E-17 under HO-0304 and burst supply line coverage) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 12: `173988e5-a8ba-4756-8c5a-06c821275dd6`

**Question:** What is a supply line as defined in HO-0304 CLAUSE WD-2?  
**is_refusal:** False  
**Top retrieval score:** 0.8637  
**Forms in top-5:** HO-0309, HO-0307, HO-0304  
**Output (first 300 chars):** `A “supply line” is any pipe or tube that carries potable water under pressure from the main service entry or from a distribution manifold to any plumbing fixture, appliance, or point of use within or attached to the described dwelling. [SOURCE: HO-0304_sa_chunk_004 | HO-0304 | CLAUSE-WD-2]`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 13: `722e6982-f4bb-4982-a7bf-5d2bbaa11237`

**Question:** What is exclusion E-36 in HO-0309?  
**is_refusal:** True  
**Top retrieval score:** 0.6827  
**Forms in top-5:** HO-0305, HO-0306, HO-0309, HO-0308, HO-0307  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. exclusion E-36 in HO-0309) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 14: `df85bab6-e848-45eb-898e-b18a1fb4ce04`

**Question:** Has subrogation been pursued on the supply-line claim from March 2024?  
**is_refusal:** True  
**Top retrieval score:** 0.5030  
**Forms in top-5:** HO-0308, HO-0309, HO-0306, HO-0304  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. subrogation on the supply-line claim) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 15: `aa6c9c68-6eb1-4579-8eeb-ebaaa4e5cc1e`

**Question:** Does HO-0306 exclude mold that results from long-term humidity?  
**is_refusal:** False  
**Top retrieval score:** 0.5575  
**Forms in top-5:** HO-0306  
**Output (first 300 chars):** `Yes. Under HO‑0306, mold losses are excluded “regardless of whether the mold or fungi results from a covered or uncovered water event,” which includes mold that develops from long‑term humidity. [SOURCE: HO-0306_sa_chunk_003 | HO-0306 | CLAUSE-MF-1]`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 16: `d923fc89-4747-4084-8b50-26625d18daea`

**Question:** What property must be scheduled under HO-0307 to receive coverage?  
**is_refusal:** True  
**Top retrieval score:** 0.6090  
**Forms in top-5:** HO-0305, HO-0309, HO-0307, HO-0304  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. property that must be scheduled under HO-0307) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 17: `1d67132f-5d28-4d60-a7a5-7220c2259d7c`

**Question:** Does exclusion E-19 appear in HO-0309 ed. 05-24 for business pursuits?  
**is_refusal:** False  
**Top retrieval score:** 0.6222  
**Forms in top-5:** HO-0306, HO-0309, HO-0307  
**Output (first 300 chars):** `Yes. Exclusion E‑19 – “Business pursuits liability” is listed in the HO‑0309 edition 05‑24 exclusion table. [ SOURCE: HO-0309_sa_chunk_007 | HO-0309 | EXCLUSION‑TABLE ]`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 18: `f6a83ee4-afe3-4edb-b783-5628a0e08e15`

**Question:** What is the reserve amount for the earth-movement claim filed last quarter?  
**is_refusal:** True  
**Top retrieval score:** 0.4408  
**Forms in top-5:** HO-0308, HO-0309  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. reserve amount for the earth-movement claim) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 19: `a4aeddb6-b266-4dad-96c9-520f212e234a`

**Question:** Is freelance consulting work excluded under HO-0309?  
**is_refusal:** True  
**Top retrieval score:** 0.4411  
**Forms in top-5:** HO-0306, HO-0309, HO-0304  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. freelance consulting work exclusion) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

### Trace 20: `047a227c-8927-4677-8bf5-cdcbaa894e61`

**Question:** Is there a per-item limit under HO-0307 for unscheduled items?  
**is_refusal:** True  
**Top retrieval score:** 0.4462  
**Forms in top-5:** HO-0309, HO-0307  
**Output (first 300 chars):** `REFUSAL: The requested information (e.g. per-item limit for unscheduled items) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.`  

**OBSERVATION:** [FILL IN — one sentence describing what you SAW]

---

## Dated Prediction

**Date:** 2026-09-05  
**Failure mode targeted:** [FILL IN — the #1 mode from taxonomy.md]  
**Specific change:** [FILL IN — e.g. 'filter retrieval by edition_date']  
**Expected delta:** [FILL IN — e.g. 'drops from X% to under Y%']  

**Git commit hash:** [PASTE COMMIT HASH HERE after `git commit`]

## Why Public Benchmarks Would Have Missed These Modes

[FILL IN — 3 sentences explaining why MMLU / HellaSwag / TruthfulQA would not surface your top-3 failure modes. Hint: your failures are about specific insurance form editions, exact exclusion codes, and citation provenance — not general knowledge.]

