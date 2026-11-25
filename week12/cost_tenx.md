# Week 12 — Cost Per Claim Triaged & 10× Catastrophe Volume Plan

## 1. Per-Claim Cost & Latency Breakdown (Span Level)

Measured on integrated run (`trace_id` traced across host agent and MCP servers):

| Span / Hop | Execution Engine | Tokens In | Tokens Out | Cost (USD) | Latency (ms) |
|---|---|---|---|---|---|
| **Hop 1: get_claim** | MCP Server (`claims-system` over stdio) | — | — | $0.000000 | 12 ms |
| **Hop 2: check_coverage_in_force** | MCP Server (`policy-search` over stdio) | — | — | $0.000000 | 8 ms |
| **Hop 3: search_policy_exclusions** | MCP Server + ChromaDB / BM25 hybrid | — | — | $0.000000 | 24 ms |
| **Hop 4: refer_to_adjuster** | MCP Server (`policy-search` over stdio) | — | — | $0.000000 | 6 ms |
| **LLM Generation (Laps 1–3)** | Groq API (`openai/gpt-oss-120b`) | ~680 | ~140 | **$0.00048** | ~1,450 ms |
| **Trace Writer + PII Redaction** | Local JSONL append (`src/tracer.py`) | — | — | $0.000000 | 3 ms |
| **TOTAL PER CLAIM TRIAGED** | **End-to-End Integrated System** | **~680** | **~140** | **$0.00048** | **~1,503 ms** |

> **Cost per Claim:** **$0.00048** (less than half of one-tenth of a cent).  
> **1,800 monthly FNOLs:** $0.86 / month in API inference cost.

---

## 2. The 10× Catastrophe Plan: A Hailstorm Week (18,000 FNOLs)

### Baseline vs. Catastrophe Surge

| Dimension | Baseline Volume (1×) | Hailstorm Week (10× Surge) | Hardware / Provider Limit | Breach Status |
|---|---|---|---|---|
| **Weekly Claims** | ~450 claims/week | **18,000 claims/week** | Unlimited storage | OK |
| **Daily Claims** | ~60 claims/day | **2,571 claims/day** | Unlimited | OK |
| **Peak Throughput** | ~2–5 claims/min | **300 claims/min (surge)** | **30 RPM** (Groq Tier 1) | **BROKEN: 10× over limit** |
| **Peak Token Flow** | ~4,100 TPM | **~246,000 TPM** | **6,000 TPM** (Groq Tier 1) | **BROKEN: 41× over limit** |
| **MCP Subprocess Forks** | ~10 forks/min | **600 process spawns/min** | OS `max_proc` / file desc | **VULNERABLE** |
| **ChromaDB Queries** | <1 QPS | **~5 QPS** | Local SQLite/Chroma: ~800 QPS | **HEALTHY** |
| **Weekly Cost** | $0.22 / week | **$8.64 / week** | $100 monthly budget | **HEALTHY** |

---

### What Breaks First: The Exact Failure Mechanism & Number

1. **The First Thing That Breaks: Groq Rate Limits (RPM & TPM)**
   - **The Number:** Groq Developer Tier caps throughput at **30 RPM** and **6,000 TPM**.
   - During a regional hailstorm or flash flood event, claims arrive in a concentrated burst: 300 claims in the first 10 minutes following the storm front.
   - At 300 RPM, the system exceeds provider RPM quotas by **1,000%** and TPM quotas by **4,100%**.
   - **Failure Signature:** Immediate HTTP `429 Too Many Requests`. Without an asynchronous queue, synchronous requests fail or queue-collapse under exponential backoff, exploding p99 latency from **1.5s to >45 seconds**, causing adjuster timeouts.

2. **The Second Thing That Breaks: Transient MCP Subprocess Exhaustion**
   - Spawning new Python interpreter subprocesses for `mcp_server_policy.py` and `mcp_server_claims.py` per agent request creates process churn (300 requests = 600 OS forks per minute).
   - Under heavy concurrency, file descriptor exhaustion (`EMFILE: too many open files`) occurs on standard Unix limits (default 256/1024 descriptors).

---

### The Remediation Architecture (Ranked & Costed)

1. **Persistent Daemonized MCP Transports (UNIX Domain Socket / FastMCP HTTP)**
   - Replace on-demand `subprocess.Popen` stdio pipes with persistent background worker daemons communicating over local unix sockets. Eliminates 600 forks/min overhead.
   - *Cost:* 0 dollars (pure architectural change).

2. **Tier-Upgrade to Groq Dedicated / Paid Provisioned Throughput (or Model Router)**
   - Upgrade to Groq Enterprise ($25/mo base or committed 500 RPM) with automatic fallback routing to an on-premise `vLLM` instance running `Qwen-2.5-72B` or `Llama-3.3-70B`.
   - *Cost:* ~$25–$80/month during catastrophe reserve months.

3. **Celery / Redis Asynchronous Buffer Queue with Dynamic Rate Throttling**
   - Ingest FNOLs into an asynchronous Redis stream. Workers consume claims at a controlled 28 RPM steady rate during storm peaks.
   - Adjusters see "Triage in progress (Position #14 in queue)" with guaranteed <60s turnaround rather than HTTP 500 drops.
   - *Cost:* ~$15/mo for managed Redis instance.

