# Week 12 — Claims Triage & Coverage Assistant: Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ENTRY POINT: python week12/run_week12.py --claim-id CLM-2024-10001          │
│              (one command, one trace_id from FNOL in to referral out)         │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ trace_id generated here, propagated to all spans
                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  W12 INTEGRATED AGENT  (src/w12_agent.py)                                    │
│  • Groq API — openai/gpt-oss-120b  ← MODEL RUNS HERE ONLY                   │
│  • Discovers tools via MCPServerPool from mcp_config.json (runtime, not code)│
│  • Budget: 8 iterations / 20K tokens / $0.15 / 90s wall-clock               │
│  • Writes per-span traces: cost + latency per hop, trace_id intact           │
│  • PII held here: redact() runs before ANY log write                         │
└──┬─────────────────────┬──────────────────────────┬───────────────────────┬─┘
   │ MCP stdio           │ MCP stdio                 │ MCP stdio             │
   ▼                     ▼                           ▼                       │
┌──────────────┐  ┌─────────────────────────────────────────────────────┐   │
│ claims-system│  │            policy-search MCP server                  │   │
│ MCP Server   │  │        (src/mcp_server_policy.py)                   │   │
│              │  │                                                      │   │
│ get_claim    │  │  search_policy_exclusions ─────► ChromaDB + BM25    │   │
│   ↓ PII      │  │    ↑ date-scoped by endorsement_set                 │   │
│  redact()    │  │                                                      │   │
│              │  │  check_coverage_in_force ──────► policy_data.py     │   │
│get_adjuster  │  │    ↑ enforces date boundary (code, not prompt hint) │   │
│  _notes      │  │    ↑ returns deductible / sub_limit / policy_limit  │   │
│   ↓ PII      │  │      as 3 DISTINCT numbers                          │   │
│  redact()    │  │                                                      │   │
└──────────────┘  │  refer_to_adjuster ─────────────► referral record  │   │
                  │    ↑ NEVER emits "covered" / "denied"               │   │
                  │    ↑ assertion enforced in eval, not just prompt     │   │
                  └─────────────────────────────────────────────────────┘   │
                                                                             │
                        ┌────────────────────────────────────────────────────┘
                        │ same trace_id
                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  TRACE WRITER  (src/tracer.py v1.2.0-week12)                                 │
│  traces.jsonl — append-only JSONL                                             │
│  Per-span record: {trace_id, span_name, latency_ms, tokens_in, tokens_out,   │
│                    cost_usd, model, pii_redacted: true}                       │
│  Redaction: claim numbers, addresses, proper names, phone numbers, injuries   │
└──────────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────────────────────────────────────────────┐
                        │  EVAL SUITE  (week12/eval_suite_w12.py)               │
                        │  35 cases total (25 from W6 + 10 W12-specific)        │
                        │  Assertions → Judge                                    │
                        │  New assertions:                                       │
                        │    • no_coverage_decision (never "claim is covered")   │
                        │    • endorsement_version_cited (clause + set + date)   │
                        │    • three_amounts_distinct (deductible ≠ sub ≠ limit) │
                        │  Judge agreement: 87%                                  │
                        │  Flood-straddle pass rate: 100% (5/5 after fix)       │
                        └───────────────────────────────────────────────────────┘

Money flow:
  Retrieval (ChromaDB + BM25 + local embeddings) ............. $0.00 / query
  LLM Generation (Groq openai/gpt-oss-120b) .................. $0.00048 / query
  Total per claim triaged ..................................... $0.00048

Where the model calls happen: ONLY in src/w12_agent.py
Where the money goes: Groq API (100% of non-zero cost)
```

## Endorsement Version Resolution (the live wound fix)

```
                    FNOL arrives with loss_date = "2024-12-31"
                              │
                              ▼
                   get_claim → policy_number
                              │
                              ▼
              check_coverage_in_force(policy_number, "2024-12-31")
                              │
                    ┌─────────┴──────────┐
                    │   policy_data.py   │
                    │                   │
                    │  2023 endorsement  │
                    │  effective_to =    │
                    │  "2024-12-31"      │
                    │                   │
                    │  2025 endorsement  │
                    │  effective_from =  │
                    │  "2025-01-01"      │
                    └─────────┬──────────┘
                              │ loss_date ≤ 2024-12-31
                              │ → returns endorsement_set = "2023"
                              ▼
              search_policy_exclusions uses "2023" wording
              → retrieves FL-3 (not FL-3A which ranks higher in vector search)
              → citation: [CLAUSE FL-3 | ENDORSEMENT 2023 | LOSS DATE 2024-12-31]
                              │
                              ▼
              Vector search alone would have returned FL-3A (2025) — WRONG
              The date filter is enforced in CODE, not as a prompt hint.
```

