# Top 3 Known Weaknesses — Wednesday Note

**Date:** Wednesday, 2026-11-11  
**Author:** AI Engineering League, Squad D (Claims Triage & Coverage Assistant)  
**Status:** Written unprompted before Thursday peer review and Friday demo

---

### Weakness 1: Calendar-Day Loss Date Boundary vs. Minute-Level Loss Timestamp

- **Description:** `check_coverage_in_force` evaluates policy in-force boundaries at date resolution (`YYYY-MM-DD`). A policy inception or endorsement transition that takes effect at `2025-01-01 00:00:01` will classify any loss dated `2024-12-31` under the 2023 endorsement set, and `2025-01-01` under the 2025 endorsement set.
- **The Vulnerability:** If an FNOL loss date is submitted as `2024-12-31` but the water ingress actually occurred at 11:58 PM on New Year's Eve continuing across midnight into 12:15 AM on `2025-01-01`, our date resolver has no timestamp granularity to split the causation window. 
- **Production Consequence:** For catastrophic storm surges spanning midnight of an endorsement rollover, adjusters must manually inspect the incident timeline. The system defaults to the recorded `date_of_loss` calendar day.

---

### Weakness 2: Heuristic Regex PII Scrubbing Across Multi-Party Adjuster Free Text

- **Description:** Our redaction layer (`src/tracer.py`) enforces strict PII scrubbing before any byte is written to `traces.jsonl` or returned over the `claims-system` MCP stdio pipe. We use regex matching for `CLM-YYYY-NNNNN`, US street address patterns, phone formats, and a title-case name heuristic on claims-related sentences.
- **The Vulnerability:** Adjuster notes frequently contain non-standard free text from contractors, handwritten police transcriptions, non-Western name structures, or single-token references (e.g. "Spoke with Dr. Rao", "Met with Dave at site", "O'Connor report pending"). While our heuristic masks standard two-token Western names (`[NAME-REDACTED]`), single-token names or unusual casing can occasionally slip past regex.
- **Production Consequence:** In Thursday's cross-squad MCP exchange, an external agent calling `get_adjuster_notes` could hypothetically observe a contractor single surname if not caught by the title-case filter. A production release requires an offline named-entity recognition (NER) transformer (e.g., Presidio / RoBERTa-NER) in the MCP egress pipeline.

---

### Weakness 3: Citation Granularity vs. Strict LLM Judge Disagreement on Endorsement Sets

- **Description:** In our integrated eval suite (`week12/eval_suite_w12.py`), the deterministic assertion requires both the specific clause ID (`FL-3` or `FL-3A`), the exact endorsement set (`2023` or `2025`), and the loss date. However, our LLM judge (`openai/gpt-oss-120b`) occasionally awards a passing grade if the assistant mentions "the 2023 policy wording" even when the strict bracketed citation tag `[CLAUSE FL-3 | ENDORSEMENT 2023 | LOSS DATE 2024-12-31]` was slightly paraphrased in prose.
- **The Vulnerability:** This creates a 13% disagreement gap between the strict deterministic parser and the LLM judge (integrated judge agreement is 87.1%, just above the 85% rubric threshold).
- **Production Consequence:** 2 out of 35 eval cases produce judge/assertion divergence where the assertion fails due to punctuation while the judge passes the semantic truth. We deliberately keep assertions ahead of judges to prevent false confidence.

