# error_before_after.md — Recoverable Error Rewrite

## Failing call: `get_claim("CLM-2024-88120")`

CLM-2024-88120 does not exist in the claims database.

---

## BEFORE — original `src/tools.py` error (opaque)

**Tool docstring (old):**
> "Retrieve claim record and adjuster notes by claim number."

**Error returned to model:**
```json
{
  "success": false,
  "error": "Claim ID 'CLM-2024-88120' does not exist in claims records."
}
```

**Model behaviour:** The model receives a generic error with no hint about
what went wrong. It cannot distinguish a typo'd claim number from a dead
claims system. It may hallucinate coverage details or report "unable to
retrieve claim" without telling the user what to fix.

---

## AFTER — `mcp_server_claims.py` error (recoverable, prompt-written docstring)

**Tool docstring (new — written as a prompt):**
> "Retrieve the full claim record — loss date, claimed amount, excess amount,
> policy form number, and adjuster notes — for a given claim number.
> Always call this FIRST to load the claim before searching exclusions or
> computing a payout.
> **Claim numbers follow the format CLM-YYYY-nnnnn (e.g. CLM-2024-10001).**
> If the number is not found the server returns the correct format so you
> can ask the caller to verify the number rather than guessing coverage."

**Error returned to model:**
```json
{
  "success": false,
  "error": "Claim CLM-2024-88120 not found. Claim numbers look like CLM-YYYY-nnnnn (e.g. CLM-2024-10001). Check the number and retry, or ask the caller to verify the claim ID."
}
```

**Model behaviour (after rewrite):** The model receives an actionable message
telling it the correct format. It can now respond to the user:
> "Claim CLM-2024-88120 was not found. Claim numbers use the format
> CLM-YYYY-nnnnn (e.g. CLM-2024-10001). Please verify the number and retry."

The error is recoverable: the model knows it's a format/ID issue, not a
system failure, and can prompt the caller to correct it without halting triage.

---

## What changed (one docstring, one error path)

| | Before | After |
|---|---|---|
| Docstring style | Noun phrase ("Retrieve claim record") | Prompt (when, how, what format, what error means) |
| Error on bad ID | `"does not exist in claims records."` | Actionable: format hint + retry instruction |
| Model recovery | Cannot distinguish typo vs dead system | Knows it's a bad ID; can guide caller to fix it |
