# Trace Replay Evidence — Week 5

**trace_id:** `468ce19a-602f-454d-b492-3cfb124569cd`  
**prompt_version:** `v1.0.0-week5`  
**model:** `openai/gpt-oss-120b`  
**model_params:** `{'temperature': 0.0, 'max_tokens': 800}`  
**timestamp:** `2026-09-05T14:19:00.233880+00:00`  
**chunks_used:** `HO-0308_sa_chunk_004`, `HO-0308_sa_chunk_007`, `HO-0308_sa_chunk_008`, `HO-0308_sa_chunk_003`, `HO-0308_sa_chunk_002`  

**PII redaction:** Claimant names and claim numbers are redacted BEFORE the trace is written (inside `tracer.py:redact()`), not after.

## Required Field Audit

| Field | Present? | Description |
|-------|----------|-------------|
| `trace_id` | ✅ | Unique trace identifier |
| `timestamp` | ✅ | ISO-8601 UTC timestamp |
| `prompt_version` | ✅ | System prompt version string |
| `question` | ✅ | User question (PII-redacted) |
| `retrieved_chunks` | ✅ | List of chunk_id + score records |
| `model` | ✅ | Model name string |
| `model_params` | ✅ | temperature, max_tokens |
| `raw_output` | ✅ | Full LLM response string |
| `is_refusal` | ✅ | Boolean refusal flag |

> All required fields present — fully replayable.

## Original Output (stored in trace)

```
Yes. HO‑0308 incorporates a concurrent‑causation rule for earth‑movement losses. CLAUSE EM‑2 states that when earth movement and a covered peril act together, the loss is excluded and coverage does not attach to any portion attributable to the covered peril [ SOURCE: HO-0308_sa_chunk_004 | HO-0308 | CLAUSE-EM-2 ]. The exclusion table also notes that the “Concurrent cause rule applies (CLAUSE EM‑2)” for the earth‑movement exclusion [ SOURCE: HO-0308_sa_chunk_007 | HO-0308 | EXCLUSION-TABLE ].
```

## Replayed Output (reconstructed from trace fields alone)

```
Yes. HO‑0308 states that when earth movement and a covered peril act together (concurrently or in sequence) to cause a loss, the entire loss is excluded under the endorsement’s concurrent‑causation rule [ SOURCE: HO-0308_sa_chunk_004 | HO-0308 | CLAUSE-EM-2 ]. This rule is also referenced in the discussion of water damage caused by ruptured pipes from earth movement, which is excluded under the same concurrent‑cause provision [ SOURCE: HO-0308_sa_chunk_008 | HO-0308 | CLAUSE-EM-3 ].
```

**Jaccard overlap:** 35.9%  
