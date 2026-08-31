#!/usr/bin/env python3
"""
chat.py — Interactive CLI chat for the Insurance Claims RAG app.

[WEEK 4 UPDATE] Now supports hybrid retrieval (BM25 + Vector + RRF) as default.
This fixes exact-token failures for queries containing exclusion codes (E-17)
and exact form numbers (HO-0304 ed. 03-24).

Type any question about the endorsements and get a grounded answer.
The app searches your indexed endorsements and generates a cited response.
Type 'quit' or 'exit' to stop.

Usage:
    source venv/bin/activate
    python3 chat.py                        # uses hybrid search (Week 4 default)
    python3 chat.py --strategy vector      # uses vector-only search (Week 3)
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load .env from the project root (if present) before anything else
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from retrieval import search as vector_search, format_results
from generation import generate_answer

# Week 4: import hybrid search (BM25 + Vector + RRF)
try:
    from hybrid_retrieval import hybrid_search
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

# ── ANSI colours ────────────────────────────────────────────────────────────
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

BANNER_TEMPLATE = """
{BOLD}{CYAN}╔══════════════════════════════════════════════════════════════╗
║       🏠  Insurance Claims RAG — Endorsement Assistant       ║
║              Week 4 Practical · Task Set D                   ║
╚══════════════════════════════════════════════════════════════╝{RESET}

{DIM}Indexed endorsements: HO-0304, HO-0305, HO-0306, HO-0307, HO-0308, HO-0309{RESET}
{DIM}Retrieval strategy : {strategy_label}{RESET}
{DIM}Type your question below. Type {BOLD}quit{RESET}{DIM} to exit.{RESET}

{YELLOW}Example questions you can ask:{RESET}
  • Does E-17 apply under HO-0304 ed. 03-24? (exact-token query — tests hybrid)
  • What is the named storm deductible under HO-0305?
  • Does HO-0306 exclude mold damage?
  • What does "sudden and accidental" mean under HO-0304?
  • Does HO-0308 cover earthquake damage?
  • Is there a business pursuits exclusion in HO-0309?
"""

SEPARATOR = f"{DIM}{'─' * 64}{RESET}"


def chat_loop(use_hybrid: bool = True):
    """
    Main chat loop.

    Args:
        use_hybrid: If True, use BM25+Vector+RRF hybrid search (Week 4 default).
                    If False, use vector-only search (Week 3 behaviour).
    """
    # Decide search function and label
    if use_hybrid and HYBRID_AVAILABLE:
        search_fn = lambda q, n: hybrid_search(q, n_results=n)
        strategy_label = f"{BOLD}Hybrid (BM25 + Vector + RRF) — Week 4{RESET}{DIM}"
    elif use_hybrid and not HYBRID_AVAILABLE:
        print(f"{YELLOW}⚠  hybrid_retrieval not found — falling back to vector search.{RESET}")
        search_fn = lambda q, n: vector_search(q, strategy="structure_aware", n_results=n)
        strategy_label = "vector-only (structure_aware) — fallback"
    else:
        search_fn = lambda q, n: vector_search(q, strategy="structure_aware", n_results=n)
        strategy_label = "vector-only (structure_aware) — Week 3"

    banner = BANNER_TEMPLATE.format(
        BOLD=BOLD, CYAN=CYAN, RESET=RESET, DIM=DIM, YELLOW=YELLOW,
        strategy_label=strategy_label,
    )
    print(banner)

    # Check API key
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print(f"{RED}⚠  GROQ_API_KEY is not set!{RESET}")
        print(f"   Copy .env.example → .env and fill in your key, then run:")
        print(f"   {BOLD}export GROQ_API_KEY=<your-key>{RESET}")
        print(f"   Then run: {BOLD}python3 chat.py{RESET}\n")
        sys.exit(1)

    turn = 0
    while True:
        turn += 1
        print(SEPARATOR)
        try:
            question = input(f"\n{BOLD}{CYAN}You:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{DIM}Goodbye!{RESET}\n")
            break

        if not question:
            print(f"{DIM}  (empty input — please type a question){RESET}")
            continue

        if question.lower() in ("quit", "exit", "q", "bye"):
            print(f"\n{DIM}Goodbye!{RESET}\n")
            break

        # ── Retrieval ──────────────────────────────────────────────────
        print(f"\n{DIM}🔍 Searching endorsements...{RESET}", end="", flush=True)
        try:
            # Fetch 7 chunks so rank-4/5 exclusion-table chunks reach the LLM
            # (PREAMBLE anchored-text prefixes cause vector similarity inflation
            # that pushes the actual answer chunk to rank 4 in hybrid mode)
            hits = search_fn(question, 7)
        except Exception as e:
            print(f"\n{RED}Retrieval error: {e}{RESET}")
            continue

        # Show which chunks were found
        print(f"\r{DIM}🔍 Found {len(hits)} relevant chunks:{RESET}")
        for h in hits[:3]:
            meta = h["metadata"]
            print(
                f"   {DIM}#{h['rank']} score={h['score']:.3f} │ "
                f"{meta.get('form_number','?')} │ "
                f"{meta.get('clause_id','?')}{RESET}"
            )
        if len(hits) > 3:
            print(f"   {DIM}... and {len(hits)-3} more{RESET}")

        # ── Generation ─────────────────────────────────────────────────
        print(f"\n{DIM}💬 Generating answer...{RESET}", end="", flush=True)
        try:
            result = generate_answer(question, hits, verbose=False)
        except Exception as e:
            print(f"\n{RED}Generation error: {e}{RESET}")
            continue

        answer = result["answer"]
        is_refusal = result["is_refusal"]

        # ── Print answer ───────────────────────────────────────────────
        print(f"\r", end="")  # clear the "Generating..." line
        if is_refusal:
            print(f"\n{BOLD}{RED}🚫 Assistant (REFUSAL):{RESET}")
            print(f"{RED}{answer}{RESET}")
        else:
            print(f"\n{BOLD}{GREEN}🤖 Assistant:{RESET}")
            print(f"{answer}")

        # ── Source hint ────────────────────────────────────────────────
        top_hit = hits[0] if hits else None
        if top_hit and not is_refusal:
            meta = top_hit["metadata"]
            print(
                f"\n{DIM}📄 Primary source: {meta.get('source_file','?')} │ "
                f"form={meta.get('form_number','?')} │ "
                f"clause={meta.get('clause_id','?')}{RESET}"
            )

    print(f"{BOLD}{CYAN}Session ended.{RESET}\n")


if __name__ == "__main__":
    # Week 4: parse --strategy flag
    parser = argparse.ArgumentParser(description="Insurance Claims RAG Chat")
    parser.add_argument(
        "--strategy",
        choices=["hybrid", "vector"],
        default="hybrid",
        help="Retrieval strategy: 'hybrid' (BM25+RRF, Week 4 default) or 'vector' (Week 3)",
    )
    args = parser.parse_args()
    chat_loop(use_hybrid=(args.strategy == "hybrid"))
