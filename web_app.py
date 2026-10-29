#!/usr/bin/env python3
"""
web_app.py — Web UI for the Insurance Claims RAG application.

A Flask web server that wraps the existing RAG pipeline
(hybrid search + generation) and serves a modern chat interface.

Usage:
    source venv/bin/activate
    python3 web_app.py
    # Open http://localhost:5000 in your browser
"""

import os
import sys
import time
import json
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from flask import Flask, request, jsonify, send_from_directory

from retrieval import search as vector_search
from generation import generate_answer

# Try to import hybrid search (Week 4)
try:
    from hybrid_retrieval import hybrid_search
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

app = Flask(__name__, static_folder="static", static_url_path="/static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main chat page."""
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "hybrid_available": HYBRID_AVAILABLE,
        "groq_key_set": bool(os.environ.get("GROQ_API_KEY", "")),
    })


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Chat endpoint — accepts a question and returns a grounded answer.

    Request JSON:
        { "question": "...", "strategy": "hybrid" | "vector" }

    Response JSON:
        { "answer": "...", "is_refusal": bool, "sources": [...], "timing": {...} }
    """
    data = request.get_json()
    question = data.get("question", "").strip()
    strategy = data.get("strategy", "hybrid")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return jsonify({"error": "GROQ_API_KEY is not set on the server"}), 500

    try:
        # -- Retrieval --
        t0 = time.time()
        if strategy == "hybrid" and HYBRID_AVAILABLE:
            hits = hybrid_search(question, n_results=7)
            strategy_used = "hybrid"
        else:
            hits = vector_search(question, strategy="structure_aware", n_results=7)
            strategy_used = "vector"
        retrieval_ms = round((time.time() - t0) * 1000)

        # -- Generation --
        t1 = time.time()
        result = generate_answer(question, hits, verbose=False)
        generation_ms = round((time.time() - t1) * 1000)

        # Build source list for the UI
        sources = []
        for h in hits[:5]:
            meta = h["metadata"]
            sources.append({
                "rank": h["rank"],
                "score": round(h["score"], 4),
                "form_number": meta.get("form_number", "?"),
                "clause_id": meta.get("clause_id", "?"),
                "source_file": meta.get("source_file", "?"),
                "snippet": h["text"][:300],
            })

        return jsonify({
            "answer": result["answer"],
            "is_refusal": result["is_refusal"],
            "sources": sources,
            "strategy_used": strategy_used,
            "timing": {
                "retrieval_ms": retrieval_ms,
                "generation_ms": generation_ms,
                "total_ms": retrieval_ms + generation_ms,
            },
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n🏠  Insurance Claims RAG — Web UI")
    print(f"   Hybrid search: {'✅ available' if HYBRID_AVAILABLE else '❌ not available'}")
    print(f"   GROQ_API_KEY:  {'✅ set' if os.environ.get('GROQ_API_KEY') else '❌ NOT SET'}")
    print(f"\n   Open http://localhost:5050 in your browser\n")
    app.run(host="0.0.0.0", port=5050, debug=True)
