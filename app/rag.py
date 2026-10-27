"""
rag.py – Simple retrieval-augmented generation helper.
Uses word-overlap (bag-of-words) scoring; no external ML libraries needed.
"""

import re
from app.db import fetch_all_refs


def _tokenise(text: str) -> set[str]:
    """Lowercase and split text into a set of words (3+ characters)."""
    return {w for w in re.findall(r"[a-z]{3,}", text.lower())}


def search(query: str, top_k: int = 5) -> list[dict]:
    """
    Return up to top_k reference snippets most relevant to the query.
    Scoring: count of overlapping tokens between query and
    (keywords joined with text).
    """
    query_tokens = _tokenise(query)
    if not query_tokens:
        return []

    refs = fetch_all_refs()
    scored = []
    for ref in refs:
        # Build a searchable string from keywords list + body text.
        corpus = " ".join(ref["keywords"]) + " " + ref["text"]
        overlap = len(query_tokens & _tokenise(corpus))
        if overlap > 0:
            scored.append((overlap, ref))

    # Sort descending by overlap score.
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ref for _, ref in scored[:top_k]]


def search_by_ids(ids: list[str]) -> list[dict]:
    """Return reference dicts for the given list of IDs."""
    refs = fetch_all_refs()
    return [r for r in refs if r["id"] in ids]
