# risk_note.md — Supply-Chain Risk: claims-system MCP server

**Who wrote it:** The claims platform team (internal, not a vetted third party); provenance and audit history are unverified before Monday's deadline.
**What it can reach:** The server process inherits the agent's environment, meaning any token or credential in `.env` (Groq API key, future DB credentials) is readable by the server's Python process at runtime.
**What it logs:** Unknown — no logging contract was provided; adjuster notes for every open claim could be silently exfiltrated if the server writes to an external sink.
**What a stolen token could do:** A compromised claims-system server could read adjuster notes on all open claims (PII, litigation strategy), replay `get_claim` against any CLM-YYYY-nnnnn, and return fabricated records that cause the agent to approve or deny claims incorrectly.
**Ship or don't:** Do not ship until the server is code-reviewed, runs in a sandboxed subprocess with no network access, and its token scope is limited to read-only claim status — adjuster notes must require a separate elevated scope with audit logging.
