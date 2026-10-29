# Week 11 — Cost Per Query by Stage

## Cost breakdown for the flagged request

| Stage | Tokens | Cost (USD) | Latency (ms) |
|---|---|---|---|
| **Retrieval** (ChromaDB + BM25 + local embeddings) | — | $0.000000 | 200ms (150ms search + 50ms embed) |
| **Tools** (Tool/Plugin calls, external search) | 0 | $0.000000 | 0ms (no tools in pure RAG pipeline) |
| **Generation input** (system + context + question) | 793 | $0.000468 | — |
| **Generation output** (LLM response) | 119 | $0.000094 | — |
| **Generation total** (Groq API, openai/gpt-oss-120b) | 912 | $0.000562 | 1200ms |
| **Total per query** | **912** | **$0.000562** | **1400ms** |

## Notes

- **Retrieval stage** runs locally: ChromaDB vector search + BM25 keyword search + sentence-transformers (`all-MiniLM-L6-v2`) embeddings run on-device → **$0.00 API cost**.
- **Tools stage** incurs **$0.00** as this pipeline does not invoke external tool endpoints or search APIs during inference.
- **Generation stage** dominates both **cost (100%)** and **latency (86%)**: Groq API pricing for `openai/gpt-oss-120b` is $0.00059/1K input tokens and $0.00079/1K output tokens.
