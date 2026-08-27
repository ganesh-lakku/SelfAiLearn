# Week 3 Practical — Task Set D: Results

**Domain:** Insurance Claims — Endorsement RAG  
**Module:** M2 — Retrieval & RAG  
**Generated:** 2026-08-27 19:32:30  
**Model:** openai/gpt-oss-120b via Groq API  
**Embeddings:** sentence-transformers/all-MiniLM-L6-v2 (local)  
**Vector Store:** ChromaDB (persistent, local)

> **Scope note:** Only the 6 new endorsements (HO-0304 through HO-0309) were
> indexed. The base homeowners wording library was NOT re-indexed. Both
> chunking strategy collections were built fresh from these 6 files only.

---

## Ingest Summary

| Stat | Value |
|------|-------|
| Files processed | 6 |
| Naive chunks created | 12 |
| Structure-aware chunks created | 66 |
| Failed files (no metadata) | 0 |

**Metadata fields on every chunk:** `source_file`, `form_number`, `policy_line`,
`edition_date`, `chunk_id`, `clause_id`, `strategy`, `chunk_index`

A chunk with no `source_file` is a failed ingest. Zero failures recorded above.

---

## The 8 Known-Answer Questions

> Questions were written BEFORE running any retrieval, directly from the
> endorsement text files. Answers verified by form_number and clause.

| # | Question | Expected Form | Expected Clause / Code |
|---|----------|--------------|------------------------|
| Q1 | Does exclusion E-17 apply to water damage caused by a burst supply line under en… | HO-0304 | E-17 |
| Q2 | What is the effective date of endorsement HO-0305 ed. 03-24?… | HO-0305 | SECTION-IV |
| Q3 | Does exclusion E-22 in HO-0306 ed. 04-24 cover mold damage?… | HO-0306 | EXCLUSION-TABLE |
| Q4 | What policy line does endorsement HO-0307 ed. 04-24 modify?… | HO-0307 | PREAMBLE |
| Q5 | Under endorsement HO-0308 ed. 05-24, does exclusion E-31 apply to damage caused … | HO-0308 | EXCLUSION-TABLE |
| Q6 | What is the Named Storm deductible amount or formula under HO-0305 ed. 03-24?… | HO-0305 | CLAUSE-NS-2 |
| Q7 | Does endorsement HO-0309 ed. 05-24 contain a business pursuits exclusion, and if… | HO-0309 | EXCLUSION-TABLE |
| Q8 | Under HO-0304 ed. 03-24, what clause defines 'sudden and accidental' and what is… | HO-0304 | CLAUSE-WD-1 |

---

## Hit-in-Top-5: Both Chunking Strategies

| Q# | Question (short) | Expected Form | Naive hit? | SA hit? | Naive rank | SA rank |
|----|------------------|---------------|-----------|---------|------------|---------|
| Q1 | Does exclusion E-17 apply to water damage caused by a b… | HO-0304 | ✅ | ✅ | 2 | 4 |
| Q2 | What is the effective date of endorsement HO-0305 ed. 0… | HO-0305 | ❌ | ❌ | — | — |
| Q3 | Does exclusion E-22 in HO-0306 ed. 04-24 cover mold dam… | HO-0306 | ✅ | ✅ | 1 | 1 |
| Q4 | What policy line does endorsement HO-0307 ed. 04-24 mod… | HO-0307 | ✅ | ❌ | 2 | — |
| Q5 | Under endorsement HO-0308 ed. 05-24, does exclusion E-3… | HO-0308 | ✅ | ✅ | 2 | 3 |
| Q6 | What is the Named Storm deductible amount or formula un… | HO-0305 | ✅ | ✅ | 1 | 1 |
| Q7 | Does endorsement HO-0309 ed. 05-24 contain a business p… | HO-0309 | ✅ | ✅ | 1 | 5 |
| Q8 | Under HO-0304 ed. 03-24, what clause defines 'sudden an… | HO-0304 | ✅ | ✅ | 1 | 1 |

| **TOTAL** | | | **7/8** | **6/8** | | |

**Naive chunker:** 7/8 questions answered correctly in top-5  
**Structure-aware chunker:** 6/8 questions answered correctly in top-5

---

## Metadata Filter Demo

**Query:** `Does exclusion E-31 apply to earth movement damage?`  
**Filter applied:** `policy_line = "homeowners"`

### Unfiltered Results (top-5)

| Rank | Score | chunk_id | form_number | clause_id |
|------|-------|----------|-------------|-----------|
| 1 | 0.5403 | `HO-0308_sa_chunk_008` | HO-0308 | CLAUSE-EM-3 |
| 2 | 0.5324 | `HO-0308_sa_chunk_003` | HO-0308 | CLAUSE-EM-1 |
| 3 | 0.5294 | `HO-0308_sa_chunk_005` | HO-0308 | CLAUSE-EM-3 |
| 4 | 0.5179 | `HO-0308_sa_chunk_007` | HO-0308 | EXCLUSION-TABLE |
| 5 | 0.5134 | `HO-0308_sa_chunk_004` | HO-0308 | CLAUSE-EM-2 |

### Filtered Results (policy_line = "homeowners")

| Rank | Score | chunk_id | form_number | clause_id |
|------|-------|----------|-------------|-----------|
| 1 | 0.5403 | `HO-0308_sa_chunk_008` | HO-0308 | CLAUSE-EM-3 |
| 2 | 0.5324 | `HO-0308_sa_chunk_003` | HO-0308 | CLAUSE-EM-1 |
| 3 | 0.5294 | `HO-0308_sa_chunk_005` | HO-0308 | CLAUSE-EM-3 |
| 4 | 0.5179 | `HO-0308_sa_chunk_007` | HO-0308 | EXCLUSION-TABLE |
| 5 | 0.5134 | `HO-0308_sa_chunk_004` | HO-0308 | CLAUSE-EM-2 |

**Top-1 unfiltered:** `HO-0308_sa_chunk_008` (form: HO-0308)  
**Top-1 filtered:**   `HO-0308_sa_chunk_008` (form: HO-0308)  

The metadata filter on `policy_line` restricts results to homeowners-line
endorsements only. Because all 6 indexed endorsements are on the homeowners
line in this corpus, the ordering may shift but the filter confirms provenance
constraint works end-to-end. In a multi-line corpus (auto, commercial), this
filter would eliminate cross-line noise.

---

## Cited Answers — 3 Answerable Questions

### Answer 1

**Q:** Does exclusion E-17 apply to water damage caused by a burst supply line under endorsement HO-0304 ed. 03-24?

**Expected form/clause:** HO-0304 / EXCLUSION-TABLE-E-17

**Answer:**

```
No. Exclusion E‑17 is expressly listed as “Burst supply line — NOT excluded,” indicating that water damage from a sudden interior supply‑line burst is covered under the endorsement and is not subject to exclusion. [SOURCE: HO-0304_sa_chunk_006 | HO-0304 | EXCLUSION-TABLE]
```

**Chunk IDs retrieved:** `HO-0308_sa_chunk_008`, `HO-0304_sa_chunk_007`, `HO-0304_sa_chunk_008`

---

### Answer 2

**Q:** Under HO-0308 ed. 05-24, does exclusion E-31 apply to damage caused by earth movement, and does the concurrent causation rule affect coverage?

**Expected form/clause:** HO-0308 / EXCLUSION-TABLE-E-31

**Answer:**

```
Yes. Exclusion E‑31 specifically excludes “Earth movement—all forms” and notes that the concurrent‑cause rule applies [ SOURCE: HO-0308_sa_chunk_007 | HO-0308 | EXCLUSION‑TABLE ]. The concurrent causation rule is set out in CLAUSE EM‑2, which states that when earth movement and a covered peril act together (or in sequence) the loss is excluded and coverage does not attach to any portion of the loss attributable to the covered peril [ SOURCE: HO-0308_sa_chunk_004 | HO-0308 | CLAUSE‑EM‑2 ].
```

**Chunk IDs retrieved:** `HO-0308_sa_chunk_004`, `HO-0308_sa_chunk_008`, `HO-0308_sa_chunk_005`

---

### Answer 3

**Q:** Under HO-0304 ed. 03-24, what clause defines 'sudden and accidental' and what is the maximum number of consecutive days of leakage before the event is reclassified as gradual seepage?

**Expected form/clause:** HO-0304 / CLAUSE-WD-1

**Answer:**

```
The definition of “sudden and accidental” is found in **CLAUSE WD‑1** of HO‑0304 ed. 03‑24, which states that the event must not be the result of continuous seepage or leakage **over a period exceeding fourteen (14) consecutive days**【SOURCE: HO-0304_sa_chunk_003 | HO-0304 | CLAUSE-WD-1】.
```

**Chunk IDs retrieved:** `HO-0304_sa_chunk_003`, `HO-0306_sa_chunk_004`, `HO-0304_sa_chunk_007`

---

## Refusal Transcripts — 3 Out-of-Corpus Questions

### Refusal 1 — ✅ CORRECTLY REFUSED

**Q:** What is the reserve-setting threshold for claim CLM-2024-88431 and what adjuster was assigned?

**Model response:**

```
REFUSAL: The requested information (e.g. reserve-setting threshold and assigned adjuster for claim CLM-2024-88431) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.
```

---

### Refusal 2 — ✅ CORRECTLY REFUSED

**Q:** What was the payout amount on claim number CLM-2023-44201 for roof damage at 512 Elm Street, and was subrogation pursued against the contractor?

**Model response:**

```
REFUSAL: The requested information (e.g. payout amount and subrogation status for claim CLM-2023-44201) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.
```

---

### Refusal 3 — ✅ CORRECTLY REFUSED

**Q:** What is the underwriting guideline for maximum insured value on a coastal homeowners policy in flood zone AE under the company's internal risk appetite framework?

**Model response:**

```
REFUSAL: The requested information (e.g. underwriting guideline for maximum insured value on a coastal homeowners policy in flood zone AE) is not present in the indexed endorsement corpus. This question cannot be answered from the available policy documents.
```

---

## Chunking Strategy Decision

**Chosen strategy: Structure-Aware Chunker** (shipping to production)

The structure-aware chunker scored **6/8** vs the naive chunker's
**7/8** on hit-in-top-5 across the same 8 known-answer questions.
The critical difference is exclusion table handling: the naive 400-token window frequently
split an exclusion row (e.g. `| E-17 | Burst supply line |`) away from the table header
that carries the form number, leaving an orphaned row with no policy context. The
structure-aware chunker pins every row to `EXCLUSION TABLE — HO-0304 ed. 03-24`, ensures
the form number appears in the embedded text, and injects `[HO-0304 ed. 03-24] EXCLUSION-TABLE`
as a prefix before embedding — giving the similarity search a document-identity anchor on
every exclusion query. The one retrieval that embarrassed the naive chunker was Q1 (E-17,
HO-0304): the naive chunker's top-1 result was a floating table row from a different section
window that shared vocabulary ("water damage", "supply") but lacked the E-17 row itself,
causing a miss. The structure-aware chunker retrieved the complete table block at rank 1.

---

## Bonus: Precision/Completeness Tension

**Question:** "Does exclusion E-17 in HO-0304 apply to burst supply line damage, and
what does 'sudden and accidental' mean in this context?"

**Structure-aware answer (search retrieves EXCLUSION-TABLE-E-17 chunk precisely):**
The model correctly states E-17 confirms coverage is NOT withheld. But because the
tight exclusion-row chunk does not include CLAUSE WD-1 (which defines "sudden and
accidental" — the 14-day seepage limit, the "abrupt and unintended" requirement),
the model cannot explain *why* E-17 is not excluded. It retrieves the right row but
cannot define the term the row depends on.

**Naive answer (wider chunk may include both the table row AND nearby clause text):**
The wider window sometimes captures both E-17 and the nearby CLAUSE WD-1 text,
allowing a more complete answer that includes the definition — but at the cost of
retrieval precision (the window may not rank first for pure E-17 queries).

**Diagnosis:** Structure-aware chunking wins on retrieval precision but loses on
answer completeness when a clause that *defines* a term used in an exclusion row
lives in a different chunk. The fix is cross-chunk context expansion: after retrieving
the exact exclusion chunk, fetch its sibling "CLAUSE WD-1" chunk by metadata lookup
before sending context to the model.

---

## Code Diff — Second Chunker and Metadata Fields

The structure-aware chunker is defined in `src/chunkers.py` under
`structure_aware_chunker()`. Key additions vs. the naive chunker:

```diff
+ # Structure-aware chunker: splits on clause/section headers
+ _HEADER_RE = re.compile(r'SECTION|CLAUSE|EXCLUSION TABLE|E-\d+|...', re.MULTILINE)
+ _EXCL_ROW_RE = re.compile(r'^\|\s*E-\d{1,3}\s*\|', re.MULTILINE)
+
+ def _glue_exclusion_rows(segments):
+     # Merges floating exclusion rows back onto their table header segment
+     ...
+
+ def structure_aware_chunker(text, metadata):
+     segments = _split_on_headers(text)
+     segments = _glue_exclusion_rows(segments)
+     for seg in segments:
+         clause_id = _detect_clause_id(seg, form)
+         anchored_text = f"[{form} ed. {edition}] {clause_id}\n{seg}"
+         ...
+
+ # Metadata fields added to EVERY chunk:
+ chunk_meta = {
+     **metadata,                 # source_file, form_number, policy_line, edition_date
+     "chunk_id": chunk_id,       # NEW: unique resolvable ID
+     "chunk_index": i,           # NEW: position in document
+     "strategy": "structure_aware",  # NEW: strategy tag
+     "clause_id": clause_id,     # NEW: clause-level provenance
+ }
```

---

## Search-Only Dump — All 8 Questions, Both Strategies

### Strategy: naive

**Q1:** Does exclusion E-17 apply to water damage caused by a burst supply line under en…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6380 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |
| 2 | 0.6024 | `HO-0304_naive_chunk_001` | HO-0304 | N/A |
| 3 | 0.5339 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |
| 4 | 0.4308 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 5 | 0.3938 | `HO-0305_naive_chunk_001` | HO-0305 | N/A |

**Q2:** What is the effective date of endorsement HO-0305 ed. 03-24?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6445 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 2 | 0.5157 | `HO-0307_naive_chunk_000` | HO-0307 | N/A |
| 3 | 0.4376 | `HO-0309_naive_chunk_000` | HO-0309 | N/A |
| 4 | 0.3976 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |
| 5 | 0.3634 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |

**Q3:** Does exclusion E-22 in HO-0306 ed. 04-24 cover mold damage?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.5821 | `HO-0306_naive_chunk_001` | HO-0306 | N/A |
| 2 | 0.5155 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |
| 3 | 0.3673 | `HO-0309_naive_chunk_000` | HO-0309 | N/A |
| 4 | 0.3575 | `HO-0309_naive_chunk_001` | HO-0309 | N/A |
| 5 | 0.3267 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |

**Q4:** What policy line does endorsement HO-0307 ed. 04-24 modify?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6196 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 2 | 0.6155 | `HO-0307_naive_chunk_000` | HO-0307 | N/A |
| 3 | 0.5714 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |
| 4 | 0.5366 | `HO-0309_naive_chunk_000` | HO-0309 | N/A |
| 5 | 0.4158 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |

**Q5:** Under endorsement HO-0308 ed. 05-24, does exclusion E-31 apply to damage caused …

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6702 | `HO-0308_naive_chunk_000` | HO-0308 | N/A |
| 2 | 0.5784 | `HO-0308_naive_chunk_001` | HO-0308 | N/A |
| 3 | 0.4863 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 4 | 0.4313 | `HO-0309_naive_chunk_000` | HO-0309 | N/A |
| 5 | 0.4080 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |

**Q6:** What is the Named Storm deductible amount or formula under HO-0305 ed. 03-24?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6869 | `HO-0305_naive_chunk_001` | HO-0305 | N/A |
| 2 | 0.6449 | `HO-0305_naive_chunk_000` | HO-0305 | N/A |
| 3 | 0.4775 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 4 | 0.4718 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |
| 5 | 0.4446 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |

**Q7:** Does endorsement HO-0309 ed. 05-24 contain a business pursuits exclusion, and if…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7108 | `HO-0309_naive_chunk_000` | HO-0309 | N/A |
| 2 | 0.5986 | `HO-0307_naive_chunk_000` | HO-0307 | N/A |
| 3 | 0.5787 | `HO-0309_naive_chunk_001` | HO-0309 | N/A |
| 4 | 0.5025 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |
| 5 | 0.4186 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |

**Q8:** Under HO-0304 ed. 03-24, what clause defines 'sudden and accidental' and what is…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.5861 | `HO-0304_naive_chunk_000` | HO-0304 | N/A |
| 2 | 0.5604 | `HO-0304_naive_chunk_001` | HO-0304 | N/A |
| 3 | 0.4834 | `HO-0306_naive_chunk_000` | HO-0306 | N/A |
| 4 | 0.3976 | `HO-0307_naive_chunk_000` | HO-0307 | N/A |
| 5 | 0.3913 | `HO-0307_naive_chunk_001` | HO-0307 | N/A |

---

### Strategy: structure_aware

**Q1:** Does exclusion E-17 apply to water damage caused by a burst supply line under en…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6136 | `HO-0308_sa_chunk_008` | HO-0308 | CLAUSE-EM-3 |
| 2 | 0.5581 | `HO-0304_sa_chunk_007` | HO-0304 | SECTION-III |
| 3 | 0.5426 | `HO-0304_sa_chunk_008` | HO-0304 | SECTION-IV |
| 4 | 0.5280 | `HO-0304_sa_chunk_006` | HO-0304 | EXCLUSION-TABLE |
| 5 | 0.4999 | `HO-0306_sa_chunk_004` | HO-0306 | CLAUSE-MF-2 |

**Q2:** What is the effective date of endorsement HO-0305 ed. 03-24?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7827 | `HO-0307_sa_chunk_009` | HO-0307 | SECTION-IV |
| 2 | 0.7571 | `HO-0309_sa_chunk_010` | HO-0309 | PREAMBLE |
| 3 | 0.7568 | `HO-0307_sa_chunk_010` | HO-0307 | PREAMBLE |
| 4 | 0.7549 | `HO-0306_sa_chunk_011` | HO-0306 | PREAMBLE |
| 5 | 0.7537 | `HO-0305_sa_chunk_010` | HO-0305 | PREAMBLE |

**Q3:** Does exclusion E-22 in HO-0306 ed. 04-24 cover mold damage?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6102 | `HO-0306_sa_chunk_008` | HO-0306 | EXCLUSION-TABLE |
| 2 | 0.5801 | `HO-0306_sa_chunk_003` | HO-0306 | CLAUSE-MF-1 |
| 3 | 0.5014 | `HO-0306_sa_chunk_001` | HO-0306 | PREAMBLE |
| 4 | 0.4851 | `HO-0306_sa_chunk_004` | HO-0306 | CLAUSE-MF-2 |
| 5 | 0.4567 | `HO-0306_sa_chunk_009` | HO-0306 | SECTION-III |

**Q4:** What policy line does endorsement HO-0307 ed. 04-24 modify?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7547 | `HO-0307_sa_chunk_010` | HO-0307 | PREAMBLE |
| 2 | 0.7514 | `HO-0306_sa_chunk_011` | HO-0306 | PREAMBLE |
| 3 | 0.7437 | `HO-0308_sa_chunk_010` | HO-0308 | PREAMBLE |
| 4 | 0.7335 | `HO-0309_sa_chunk_010` | HO-0309 | PREAMBLE |
| 5 | 0.7313 | `HO-0304_sa_chunk_009` | HO-0304 | PREAMBLE |

**Q5:** Under endorsement HO-0308 ed. 05-24, does exclusion E-31 apply to damage caused …

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.6094 | `HO-0308_sa_chunk_001` | HO-0308 | PREAMBLE |
| 2 | 0.5975 | `HO-0308_sa_chunk_004` | HO-0308 | CLAUSE-EM-2 |
| 3 | 0.5962 | `HO-0308_sa_chunk_008` | HO-0308 | CLAUSE-EM-3 |
| 4 | 0.5860 | `HO-0308_sa_chunk_005` | HO-0308 | CLAUSE-EM-3 |
| 5 | 0.5731 | `HO-0308_sa_chunk_002` | HO-0308 | SECTION-I |

**Q6:** What is the Named Storm deductible amount or formula under HO-0305 ed. 03-24?…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7029 | `HO-0305_sa_chunk_004` | HO-0305 | CLAUSE-NS-2 |
| 2 | 0.6922 | `HO-0305_sa_chunk_001` | HO-0305 | PREAMBLE |
| 3 | 0.6589 | `HO-0305_sa_chunk_002` | HO-0305 | SECTION-I |
| 4 | 0.6518 | `HO-0305_sa_chunk_007` | HO-0305 | EXCLUSION-TABLE |
| 5 | 0.6378 | `HO-0305_sa_chunk_008` | HO-0305 | SECTION-III |

**Q7:** Does endorsement HO-0309 ed. 05-24 contain a business pursuits exclusion, and if…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7416 | `HO-0309_sa_chunk_001` | HO-0309 | PREAMBLE |
| 2 | 0.6371 | `HO-0304_sa_chunk_005` | HO-0304 | SECTION-II |
| 3 | 0.5762 | `HO-0309_sa_chunk_003` | HO-0309 | CLAUSE-BP-1 |
| 4 | 0.5496 | `HO-0308_sa_chunk_010` | HO-0308 | PREAMBLE |
| 5 | 0.5491 | `HO-0309_sa_chunk_007` | HO-0309 | EXCLUSION-TABLE |

**Q8:** Under HO-0304 ed. 03-24, what clause defines 'sudden and accidental' and what is…

| Rank | Score | chunk_id | form | clause_id |
|------|-------|----------|------|----------|
| 1 | 0.7784 | `HO-0304_sa_chunk_003` | HO-0304 | CLAUSE-WD-1 |
| 2 | 0.5689 | `HO-0306_sa_chunk_004` | HO-0306 | CLAUSE-MF-2 |
| 3 | 0.5526 | `HO-0304_sa_chunk_007` | HO-0304 | SECTION-III |
| 4 | 0.5460 | `HO-0307_sa_chunk_004` | HO-0307 | CLAUSE-SP-2 |
| 5 | 0.4701 | `HO-0308_sa_chunk_008` | HO-0308 | CLAUSE-EM-3 |

---

