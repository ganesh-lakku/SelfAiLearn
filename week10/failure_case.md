# failure_case.md — Week 10 Worker Failure Injection

## Injected Failure

- **Claim:** CLM-2024-10003
- **Failure:** Coverage/exclusions worker returned HTTP 500 (simulated)
- **Trigger:** `inject_failure_on_claim_id="CLM-2024-10003"` in `run_orchestrator()`

## Claim Details

| Field | Value |
|-------|-------|
| Form | HO-0305 |
| Description | Named storm wind damage — covered under HO-0305 with storm deductible. |
| Expected Status | COVERED |
| Expected Payout | $7500.00 |

## Orchestrator Actual Behaviour

> **DEGRADED TO PARTIAL ANSWER (incorrect — over-denied)**

| Field | Value |
|-------|-------|
| Coverage worker succeeded | False |
| Degraded mode activated | True |
| Orchestrator final status | DENIED |
| Orchestrator payout | $0.00 |
| Judge verdict | FAIL ❌ |

## Hand-off Sequence During Failure

```
  [request             ] orchestrator → coverage_worker  |  14 tokens  |  Request coverage decision for CLM-2024-10003
  [response            ] coverage_worker → orchestrator  |  80 tokens  |  ERROR: HTTP 500 Internal Server Error — coverage worker unavailable
  [request             ] orchestrator → adjuster_summary_worker  |  15 tokens  |  Request adjuster note summary for CLM-2024-10003
  [response            ] adjuster_summary_worker → orchestrator  |  79 tokens  |  CauseOfLoss='' Trigger='None' tokens=552
  [synthesis_request   ] orchestrator → orchestrator_synthesis_llm  |  352 tokens  |  Orchestrator synthesises worker outputs; re-sends both payloads to LLM
  [synthesis_response  ] orchestrator_synthesis_llm → orchestrator  |  54 tokens  |  Final decision: status=DENIED excl=None degraded=True
  [final_result        ] orchestrator → caller  |  9 tokens  |  Final: status=DENIED payable=$0.00 degraded=True
```

## Behaviour Classification

✅ **RETRIED**: Not applicable here — the 500 was immediate, no retry was attempted. The orchestrator correctly detected the failure.

⚠️ **DEGRADED TO PARTIAL ANSWER**: The orchestrator detected the coverage worker 500, activated degraded mode, and used only the adjuster-summary worker output to make the coverage decision. It did NOT retry the failed worker. The synthesis LLM was explicitly told the coverage worker failed.



## One-Line Summary

**Orchestrator behaviour on injected 500: DEGRADED to partial answer using adjuster-summary worker only — did not retry, did not lie about coverage.**

## A2A Task Lifecycle Mapping (Bonus)

Under the A2A protocol task lifecycle, this case should have ended in:

**`failed`** — not `paused at input-required`.

Rationale: the coverage worker 500 was a server-side internal error, not a missing user
input. `input-required` applies when the orchestrator needs additional information from
the caller (e.g., adjuster confirms coverage intent). A 500 from a worker is a
`failed` terminal state; the orchestrator should surface the error to the caller and
let the caller decide whether to retry or escalate.

**What A2A buys over a plain REST call:**  
A2A task lifecycle states (submitted → working → failed/completed) give the orchestrator
a first-class way to distinguish transient worker failures from permanent ones and to
propagate partial results with structured error context — a plain REST 500 gives you
only an HTTP status code with no task state machine to pause, inspect, or resume.
