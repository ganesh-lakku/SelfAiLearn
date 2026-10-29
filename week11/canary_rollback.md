# Canary & Rollback Plan

## Prompt version bump

- **Before**: `v1.0.0-week5`
- **After**:  `v1.1.0-week11`
- **Change**: Added rules 7–8 (EXCLUSION CHECK) to the system prompt

## Canary plan (2 lines)

1. Route 10% of traffic to `v1.1.0-week11` for 24h; alert if refusal rate jumps >15% above baseline (false-positive exclusion checks) or if any coverage-affirm answer lacks an E-XX citation when the context contains an EXCLUSION TABLE chunk.
2. If canary passes, promote to 100%; if it fails, revert `PROMPT_VERSION` to `v1.0.0-week5` and re-deploy within 5 minutes.

## Rollback plan (2 lines)

1. Set `PROMPT_VERSION = "v1.0.0-week5"` in `src/tracer.py` and restore `SYSTEM_PROMPT` in `src/generation.py` to the pre-fix version (git revert the commit).
2. Re-deploy; verify the W11-1 eval case fails (confirming rollback is real) then file a ticket to investigate false-positive rate before re-attempting the fix.
