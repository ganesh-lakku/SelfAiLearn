# Week 11 — Drill Report

## Complaint
> "An adjuster says it told a claimant something was covered when the
> policy excludes it, sometime yesterday."

## Result

| Field | Value |
|---|---|
| **Time-to-find** | **01:42** (mm:ss) |
| **Timed by** | Alex Rivera (Squadmate, Squad D) |
| **Slice used** | TIME (last 48h) + OUTPUT (coverage-affirming language) + CONTEXT (exclusion domain match without E-XX code) |
| **Trace ID** | `d7119375-11a5-443f-94b3-bce5119a905d` |
| **Timestamp** | 2026-10-28T17:55:37.346725+00:00 |
| **Question** | Is mold from HVAC condensation covered under HO-0306? |
| **Suspects found** | 8 total, 8 high |

## The failure

The model told a claimant that mold from HVAC condensation **is covered**
under HO-0306 (CLAUSE MF-2 remediation sublimit exception), but **ignored
exclusion E-27** which explicitly excludes "Mold from HVAC condensation
(chronic)" when the HVAC system was not serviced in 3 years.

## Slicing strategy

1. **TIME slice**: Filtered to traces from the last 48 hours ("sometime yesterday")
2. **OUTPUT slice**: Searched `raw_output` for coverage-affirming language ("is covered", "will pay")
3. **CONTEXT slice**: Cross-checked against exclusion domain keywords without E-XX codes in the output

The combination of OUTPUT + CONTEXT slicing was what found it: the answer
affirmed coverage in a known exclusion domain (mold) without citing any
exclusion code.

## Missing log field that would have made this instant

The trace does not log `per_span_latency` or `exclusion_codes_checked` as
separate indexed fields. Adding an `exclusion_codes_in_context` field to
every trace would allow a single `grep` to find any answer where the
retrieved context contained exclusion codes but the output did not cite them.
