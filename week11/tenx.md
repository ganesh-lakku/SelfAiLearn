# Week 11 — 10x Volume Analysis

## One-line answer

**At 10x today's claim volume, rate limits break first: Groq's free tier caps throughput at 30 RPM and 6,000 TPM, so a 10x surge from 5 to 50 peak RPM triggers immediate HTTP 429 quota exhaustion, which cascades into 8–15s queued tail latency.**

---

## The Numbers

| Metric | Current (1x Baseline) | At 10x Surge | Provider Threshold / Limit | Failure Status |
|---|---|---|---|---|
| **Daily Query Volume** | ~50 queries/day | ~500 queries/day | Unlimited | Healthy |
| **Daily LLM Cost** | $0.0281 / day | $0.2810 / day | Budget-dependent ($100/mo) | Healthy (negligible cost) |
| **Peak Throughput (RPM)** | ~5 RPM | **~50 RPM** | **30 RPM** (Groq Tier 1) | **BROKEN (Exceeds quota by 67%)** |
| **Peak Token Flow (TPM)** | ~4,560 TPM | **~45,600 TPM** | **6,000 TPM** (Groq Tier 1) | **BROKEN (Exceeds quota by 660%)** |
| **p50 Latency** | 1200 ms | 1200 ms | 2,000 ms SLA | Healthy (when not throttled) |
| **p99 Latency (Queued)** | ~1400 ms | **8,000–15,000 ms** | 5,000 ms SLA | **BROKEN (Retry backoff inflates tail)** |

---

## Why Rate Limits Break First (Not Cost or Compute)

1. **Cost is trivial**: At $0.000562 per query, even 500 claims/day costs only **$0.28/day** (~$8.43/month). Financial budget is never the initial bottleneck.
2. **Compute is not the bottleneck**: ChromaDB and BM25 run locally in <15ms and easily scale to thousands of local reads/sec.
3. **Provider Quotas fail immediately**: Groq free/developer tier limits requests to **30 RPM** and **6,000 TPM**. Under normal traffic (~5 RPM, ~4,560 TPM), requests pass. At 10x (50 queries in a 10-minute burst = 50 RPM, 45,600 TPM), requests instantly return **HTTP 429 Too Many Requests**. Exponential retry backoff then causes requests to stack up, blowing p99 latency past the 5-second adjuster SLA to **8–15 seconds**.
