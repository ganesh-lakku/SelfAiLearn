# Week 12 Capstone — Claims Triage & Coverage Assistant (Variant D)

> **Soft Suave · The AI Engineering League**  
> **Gate:** M6 — End-to-end app + closed loop → AI Summit & certification  
> **Domain:** Insurance claims triage, temporal policy wording resolution, MCP integration, and compliance guardrails.

---

## ⚡ Quickstart — One Command Runs Everything

A stranger can clone and run the integrated system end to end with one command:

```bash
# 1. Clone & enter
git clone https://github.com/ganesh-lakku/SelfAiLearn.git
cd SelfAiLearn

# 2. Activate virtual environment & configure API key
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your-groq-api-key"   # or set in .env

# 3. RUN THE INTEGRATED CAPSTONE (One command)
python3 week12/run_week12.py
```

### Options:
- `python3 week12/run_week12.py --claim-id CLM-2024-77202`: Live triage of flood straddle claim (loss date: 2024-12-31)
- `python3 week12/run_week12.py --eval-only`: Run the 35-case integrated eval suite (assertions + LLM judge)
- `python3 week12/run_week12.py --trajectory-only`: Run the 15-case trajectory evaluation suite

---

## 🏛️ Week 12 Capstone Artifacts & Submission Index

| Item / Rubric Criterion | File Location | Key Metric / Deliverable |
|---|---|---|
| **One-Page Architecture Sketch** | [`week12/architecture.md`](week12/architecture.md) | Agent, MCP stdio hops, ChromaDB, Groq model routing, money flow |
| **Tuesday's Unedited Seam List** | [`week12/seam_list.md`](week12/seam_list.md) | 10 integration seams marked fixed / accepted / ran-out-of-time |
| **Integrated Evaluation Suite** | [`week12/eval_suite_w12.py`](week12/eval_suite_w12.py) | 35 cases, assertions before judges, **87.1% judge agreement** |
| **Re-Scored Error Taxonomy** | [`week12/taxonomy_w12.md`](week12/taxonomy_w12.md) | 6 modes; integration mode: `wrong_endorsement_version` (15%) |
| **Trajectory Evaluation & Gap** | [`week12/trajectory_w12.py`](week12/trajectory_w12.py) | **80.0% tool-choice accuracy**, **+20.0% outcome gap** |
| **Wednesday's Known Weaknesses** | [`week12/weaknesses.md`](week12/weaknesses.md) | Top 3 weaknesses written unprompted before Thursday peer review |
| **Cost & 10× Catastrophe Plan** | [`week12/cost_tenx.md`](week12/cost_tenx.md) | **$0.00048/claim**; 18,000 FNOL hailstorm week breaks Groq RPM first |
| **10-Minute Demo Script** | [`week12/demo_script.md`](week12/demo_script.md) | Four-part standard timed script (0:00–10:00) |
| **Integrated Agent & Tracing** | [`src/w12_agent.py`](src/w12_agent.py) | Per-span traces with intact trace_id surviving agent and MCP hops |
| **Policy In-Force & Date Filter** | [`src/policy_data.py`](src/policy_data.py) | Code-enforced date filter resolving 2023 vs 2025 flood exclusion |

---

## 🎯 The Compliance & Regulatory Core

1. **Never Decides Coverage:** The assistant strictly surfaces facts, policy wording, and citations. Final verdict tool is `refer_to_adjuster`. The system never states "claim is covered" or "claim is denied".
2. **Date-In-Force Resolution (The Live Wound):** An August 2024 or December 31, 2024 loss is assessed strictly against the **2023 endorsement wording** (`FL-3`, threshold-based), *never* the 2025 wording (`FL-3A`), even though the 2025 document ranks higher in vector search similarity.
3. **Three Distinct Numbers:** Deductible, sub-limit, and policy limit are kept as three separate schema fields.
4. **Zero-PII MCP Line:** Claimant names, street addresses, and bodily injury descriptions are stripped via `redact()` before logging to `traces.jsonl` or passing over MCP pipes to peer squads.

---

## 📊 A Number That Moved

- **Wrong Endorsement Version Citation Rate on Flood Boundary Cases ($n=5$):**
  - **Before Date Filter:** **60.0%** (3/5 straddle cases cited 2025 wording for a 2024 loss)
  - **After Code Date Filter:** **0.0%** (0/5 straddle cases cited wrong wording; 5/5 green)
- **Judge Agreement Rate on Integrated Outputs:** **87.1%** (exceeds the 85% requirement)
- **Stated Non-Coverage:** The test suite does *not* cover multi-policy concurrent causation conflicts where two separate policies apply simultaneously across endorsement rollover dates.

---

## 🚀 Getting Started (After Cloning)

Follow these steps on any machine after cloning this repo:

### 1. Clone the repository
```bash
git clone https://github.com/ganesh-lakku/SelfAiLearn.git
cd SelfAiLearn
```

### 2. Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your API key
```bash
cp .env.example .env
```
Open `.env` and replace the placeholder with your real Groq API key:
```
GROQ_API_KEY=gsk_your_actual_key_here
```
> Get a free key at https://console.groq.com/keys

### 5. Build the vector index
```bash
python3 src/ingest.py
```
This creates the `chroma_db/` vector store locally (not in git).

### 6. Run the full evaluation pipeline
```bash
python3 run_all.py
```
Produces `results.md` with all evaluation evidence.

### 7. (Optional) Launch the interactive chat
```bash
python3 chat.py
```

---

## 📁 Project Structure

```
├── .env.example                # API key template — copy to .env
├── .gitignore
├── endorsements/               # 6 synthetic homeowners endorsements
│   ├── HO-0304_03-24.txt      # Water damage + supply line coverage
│   ├── HO-0305_03-24.txt      # Named storm deductible
│   ├── HO-0306_04-24.txt      # Mold and fungi exclusion
│   ├── HO-0307_04-24.txt      # Scheduled personal property
│   ├── HO-0308_05-24.txt      # Earth movement exclusion (broadened)
│   └── HO-0309_05-24.txt      # Business pursuits exclusion
├── src/
│   ├── chunkers.py             # Naive + structure-aware chunkers
│   ├── ingest.py               # ChromaDB ingest with metadata
│   ├── retrieval.py            # Vector search + metadata filter
│   ├── generation.py           # Groq LLM generation + hard refusal
│   └── evaluate.py             # 8-question evaluation harness
├── chat.py                     # Interactive CLI chat
├── run_all.py                  # Master runner
└── results.md                  # Auto-generated deliverable
```

> **Note:** `chroma_db/`, `venv/`, `.env`, and `__pycache__/` are excluded from git via `.gitignore` and must be created locally.

---

## 🛠 Technology Stack

| Component | Technology |
|-----------|-----------|
| LLM (generation) | openai/gpt-oss-120b via Groq API |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| Vector store | ChromaDB (persistent, local) |
| Chunking A | Naive sliding window (400 tokens, 50 overlap) |
| Chunking B | Structure-aware (splits on clause/section headers) |
| Python | 3.10+ |

---

## Key Design Decisions

### Chunking Strategy A — Naive
Fixed 400-token sliding window with 50-token overlap. No awareness of
document structure, headers, or table boundaries.

### Chunking Strategy B — Structure-Aware
Splits on form/clause headers (`SECTION`, `CLAUSE`, `EXCLUSION TABLE`, `E-NN`).
Never separates an exclusion table row from its table header. Injects
`[form_number ed. edition_date] clause_id` as a text prefix before embedding.

### Metadata Schema
Every chunk carries:
- `source_file` — original filename
- `form_number` — e.g., HO-0304
- `edition_date` — e.g., 03-24
- `policy_line` — e.g., homeowners
- `chunk_id` — unique, resolvable identifier
- `clause_id` — e.g., EXCLUSION-TABLE-E-17
- `strategy` — naive | structure_aware
- `chunk_index` — position within document

### Refusal Guarantee
The generation system prompt contains a hard refusal rule: if the answer
is not in the indexed context, the model MUST output a specific REFUSAL
message. "Use your best judgment" is explicitly prohibited.

## Scope Constraint
Only the 6 new endorsements are indexed. The base wording library is NOT
re-indexed (per assignment requirement).
