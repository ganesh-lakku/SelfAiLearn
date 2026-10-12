# verdict.md — Week 10 Keep or Kill Decision

## Verdict: KILL

The orchestrator is cheaper (0.6x tokens, $0.00193 vs $0.00271 per claim) and faster (p50 17.5s vs 24.6s) — but its pass rate dropped 10pp (90% vs 100%) because the coverage worker 500 caused an over-denial on a valid named-storm claim. A wrongful denial at production scale costs more than the token savings.

## Two Numbers That Drive This Decision

1. **Pass Rate**: Single agent **100.0%** vs Orchestrator **90.0%**  
   Delta = **−10.0pp** — single agent wins. One wrongful denial per 10 claims is unacceptable in claims operations where each false denial triggers a complaint and regulatory exposure.

2. **Cost per Claim**: Single agent **$0.00271** vs Orchestrator **$0.00193**  
   The orchestrator is 29% cheaper and uses only **0.6x the tokens** (24,078 vs 41,743). The single agent's iterative context re-submission inflates its token bill — but this advantage is erased by the 10pp pass-rate deficit.

## Sunk-Cost Bias — Named Out Loud

> **We built the orchestrator. It took engineering time. There is a temptation to declare it the winner because it is cheaper and faster, to justify that investment. This is sunk-cost bias. The engineering hours are already spent regardless of the verdict. The only rational question is: do these four numbers justify running it in production on the next 10,000 claims? At 90% pass rate, 1,000 wrongful denials per 10,000 claims is not a cost saving — it is a liability.**

## Context Re-Send Multiplier

Context re-send multiplier = **0.6x** (orchestrator 24,078 tokens / single-agent 41,743 tokens).  
Dominant hand-off: `orchestrator → orchestrator_synthesis_llm [synthesis_request]`, **3,295 tokens (53.8% of all orchestrator tokens)**.  
Note: 0.6x means the orchestrator is *more* token-efficient, not less — the single agent re-submits the full conversation history on every lap, compounding tokens quadratically.

## Latency

| Metric | Single Agent | Orchestrator | Winner |
|--------|-------------|--------------|--------|
| p50    | 24.621s | 17.486s | Orchestrator (1.4x faster) |
| p99    | 35.299s | 21.16s | Orchestrator (1.7x faster) |

The p99 is the claim that gets complained about. Report both. Orchestrator wins on latency — but latency does not override correctness.

## What Would Change the Verdict

Fix the coverage-worker retry or fallback logic: if the worker returns a 5xx, retry once before degrading. Or, in degraded mode, default to a **`input-required`** A2A state rather than guessing DENIED — force an adjuster confirmation before finalising. That change would preserve the token and latency gains while eliminating the wrongful-denial risk.

## Final Line

**KILL** (as-is): Pass rate 90% vs 100%, one wrongful denial per 10 claims — the $0.00078/claim cost saving does not offset the liability. Fix the failure-mode, then re-race.
