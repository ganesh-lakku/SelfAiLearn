# Week 3 Practical — Task Set D: Insurance Claims RAG

## Overview
This project implements a Retrieval-Augmented Generation (RAG) pipeline for
insurance claims, specifically for evaluating two chunking strategies on
homeowners policy endorsements.

## Quick Start

```bash
# 1. Activate the virtual environment
source venv/bin/activate

# 2. Set your Groq API key (for generation only — embeddings are local)
export GROQ_API_KEY=gsk_...

# 3. Run the full pipeline
python3 run_all.py
```

The pipeline will produce `results.md` with all required evidence.

## Project Structure

```
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
├── chroma_db/                  # Persistent vector store (auto-created)
├── run_all.py                  # Master runner
├── results.md                  # Auto-generated deliverable
└── README.md
```

## Technology Stack

| Component | Technology |
|-----------|-----------|
| LLM (generation) | openai/gpt-oss-120b via Groq API |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local) |
| Vector store | ChromaDB (persistent) |
| Chunking A | Naive sliding window (400 tokens, 50 overlap) |
| Chunking B | Structure-aware (splits on clause/section headers) |
| Python | 3.14 (system venv) |

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
