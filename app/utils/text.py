from __future__ import annotations

import re

from app.core.constants import STOP_WORDS


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def to_excerpt(text: str, *, max_length: int = 220) -> str:
    cleaned = normalize_whitespace(text)
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def keyword_overlap(query: str, candidate: str) -> int:
    query_terms = set(_keywords(query))
    candidate_terms = set(_keywords(candidate))
    return len(query_terms & candidate_terms)


def is_useful_retrieval(query: str, candidate: str, score: float, *, threshold: float) -> bool:
    if keyword_overlap(query, candidate) > 0:
        return True
    return score <= threshold


def _keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [token for token in tokens if token not in STOP_WORDS]
