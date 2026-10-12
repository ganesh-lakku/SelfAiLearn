# race_table.md — Week 10 Practical Task Set D
## Single Agent vs Orchestrator: 4 Metrics × 2 Arms

**Domain:** Insurance Claims — Homeowners Endorsements  
**Week:** 10 — Multi-Agent & A2A — With Evidence, Not Fashion  
**Generated:** 2026-10-12 19:14:21  
**Eval set:** Same 10 Week-6/7 claims (CLM-2024-10001 through CLM-2024-10010)  
**Judge:** Deterministic — status match + payout within $0.01  

---

## Summary Table: 4 Metrics × 2 Arms

| Metric | Single Agent | Orchestrator | Winner |
|--------|-------------|--------------|--------|
| **Pass Rate** | **100.0%** (10/10) | **90.0%** (9/10) | Single Agent |
| **p50 Latency** | **24.621s** | **17.486s** | Orchestrator |
| **p99 Latency** | **35.299s** | **21.16s** | Orchestrator |
| **Total Tokens** | **41743** | **24078** | Orchestrator |
| **Cost per Claim** | **$0.00271** | **$0.00193** | Orchestrator |

---

## Context Re-Send Multiplier

> Context re-send multiplier = 0.6x (orchestrator 24078 / single 41743 tokens). Dominant hand-off: orchestrator → orchestrator_synthesis_llm [synthesis_request], 3295 tokens (53.8% of all).

---

## Per-Claim Breakdown (Same 10 Cases)

| Claim ID | Expected (status / payout) | Agent Result | Agent Tokens | Agent Lat | Orch Result | Orch Tokens | Orch Lat |
|----------|---------------------------|--------------|-------------|-----------|-------------|-------------|----------|
| `CLM-2024-10001` | COVERED / $1700.00 | `COVERED` / $1700.00 ✅ | 2899 | 3.04s | `COVERED` / $1700.00 ✅  | 2303 | 13.88s |
| `CLM-2024-10002` | DENIED / $0.00 | `DENIED` / $0.00 ✅ | 4585 | 13.31s | `DENIED` / $0.00 ✅  | 2827 | 19.08s |
| `CLM-2024-10003` | COVERED / $7500.00 | `COVERED` / $7500.00 ✅ | 2780 | 1.79s | `DENIED` / $0.00 ❌ ⚠️ DEGRADED | 1271 | 11.31s |
| `CLM-2024-10004` | COVERED / $5000.00 | `COVERED` / $5000.00 ✅ | 5127 | 31.00s | `COVERED` / $5000.00 ✅  | 2296 | 12.78s |
| `CLM-2024-10005` | DENIED / $0.00 | `DENIED` / $0.00 ✅ | 4787 | 31.34s | `DENIED` / $0.00 ✅  | 2788 | 18.15s |
| `CLM-2024-10006` | COVERED / $3700.00 | `COVERED` / $3700.00 ✅ | 4877 | 31.71s | `COVERED` / $3700.00 ✅  | 2316 | 17.93s |
| `CLM-2024-10007` | DENIED / $0.00 | `DENIED` / $0.00 ✅ | 4686 | 35.30s | `DENIED` / $0.00 ✅  | 2823 | 21.16s |
| `CLM-2024-10008` | DENIED / $0.00 | `DENIED` / $0.00 ✅ | 4541 | 26.65s | `DENIED` / $0.00 ✅  | 2668 | 20.30s |
| `CLM-2024-10009` | COVERED / $0.00 | `COVERED` / $0.00 ✅ | 2982 | 10.60s | `COVERED` / $0.00 ✅  | 2478 | 17.04s |
| `CLM-2024-10010` | DENIED / $0.00 | `DENIED` / $0.00 ✅ | 4479 | 22.59s | `DENIED` / $0.00 ✅  | 2308 | 13.23s |

---

## Notes

- **Failure injection**: CLM-2024-10003 had the coverage worker forced to return HTTP 500.
  The orchestrator ran in degraded mode (summary worker only) for that claim.
  See `failure_case.md` for the full behaviour record.
- **Same judge**: pass = exact status match + payout within $0.01. No changed ruler.
- **Same 10 cases**: eval_cases from Week 6/7 golden set, unchanged.
