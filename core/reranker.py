#!/usr/bin/env python3
"""
reranker.py — Cross-encoder reranking for moonshine memory retrieval.

Takes initial search results (from FTS5/embedding/graph) and re-scores each
against the query using a cross-encoder model for improved precision.

Uses sentence-transformers CrossEncoder (ms-marco-MiniLM-L-6-v2) locally.
Falls back gracefully if the model isn't available — returns original order.

Environment:
    MOONSHINE_RERANK        Enable reranking (default: false)
    MOONSHINE_RERANK_MODEL  Cross-encoder model (default: cross-encoder/ms-marco-MiniLM-L-6-v2)
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("moonshine.reranker")

# ============ Config ============

RERANK_ENABLED = os.environ.get("MOONSHINE_RERANK", "false").lower() in ("true", "1", "yes")
RERANK_MODEL = os.environ.get("MOONSHINE_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# ============ Lazy Model Loading ============

_cross_encoder = None
_load_attempted = False
_load_error: Optional[str] = None


def _ensure_venv_packages():
    """Try to add the local .venv site-packages to sys.path if not already importable."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        pass

    # Check for a .venv next to this file (core/.venv)
    venv_dir = Path(__file__).parent / ".venv"
    if not venv_dir.exists():
        return False

    # Find the site-packages inside the venv
    for sp in venv_dir.glob("lib/python*/site-packages"):
        if str(sp) not in sys.path:
            sys.path.insert(0, str(sp))

    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _load_model():
    """Lazy-load the cross-encoder model. Called once on first rerank request."""
    global _cross_encoder, _load_attempted, _load_error
    if _load_attempted:
        return _cross_encoder

    _load_attempted = True

    if not _ensure_venv_packages():
        _load_error = "sentence-transformers not installed (run: cd core && python3 -m venv .venv && source .venv/bin/activate && pip install sentence-transformers)"
        logger.warning(f"Reranker unavailable: {_load_error}")
        return None

    try:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder(RERANK_MODEL)
        logger.info(f"Reranker loaded: {RERANK_MODEL}")
        return _cross_encoder
    except Exception as e:
        _load_error = f"Failed to load cross-encoder model: {e}"
        logger.warning(f"Reranker unavailable: {_load_error}")
        return None


# ============ Public API ============


def is_available() -> bool:
    """Check if reranking is enabled and the model can load."""
    if not RERANK_ENABLED:
        return False
    return _load_model() is not None


def get_status() -> dict:
    """Return reranker status for diagnostics."""
    return {
        "enabled": RERANK_ENABLED,
        "model": RERANK_MODEL,
        "loaded": _cross_encoder is not None,
        "error": _load_error,
    }


def rerank(
    query: str,
    results: list[tuple],
    top_k: Optional[int] = None,
    score_key: str = "rerank_score",
) -> list[tuple]:
    """
    Rerank search results using a cross-encoder.

    Args:
        query:     The search query string.
        results:   List of (score, row_dict) tuples from initial retrieval.
                   row_dict must have 'title' and optionally 'content'.
        top_k:     Return only top K results after reranking (None = return all).
        score_key: Key name to add to each row_dict with the cross-encoder score.

    Returns:
        Re-sorted list of (original_score, row_dict) tuples, with score_key added
        to each row_dict. If reranker is unavailable, returns the original list
        unchanged (graceful fallback).
    """
    if not results:
        return results

    if not RERANK_ENABLED:
        return results

    model = _load_model()
    if model is None:
        # Graceful fallback: return original order unchanged
        return results

    # Build (query, document) pairs for the cross-encoder
    pairs = []
    for _score, row in results:
        # Combine title + content for richer cross-encoder input
        title = row.get("title", "")
        content = row.get("content", "")
        doc_text = f"{title}\n{content}" if content else title
        # Truncate to avoid excessive input (cross-encoders have ~512 token limit)
        doc_text = doc_text[:1000]
        pairs.append([query, doc_text])

    try:
        # Score all pairs in one batch call (efficient)
        ce_scores = model.predict(pairs)

        # Attach scores to results
        scored = []
        for i, (orig_score, row) in enumerate(results):
            row[score_key] = round(float(ce_scores[i]), 4)
            scored.append((orig_score, row))

        # Sort by cross-encoder score (descending)
        scored.sort(key=lambda x: x[1][score_key], reverse=True)

        if top_k is not None:
            scored = scored[:top_k]

        return scored

    except Exception as e:
        logger.error(f"Reranking failed, returning original order: {e}")
        return results
