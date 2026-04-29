from __future__ import annotations

import re

from app.core.constants import STOP_WORDS

TEXT_REPLACEMENTS = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\ufb01": "fi",
        "\ufb02": "fl",
    }
)
DOSAGE_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|g|ml|tablets?|capsules?|pills?)\b", re.IGNORECASE)
TREATMENT_PATTERN = re.compile(
    r"\b("
    r"dose|dosage|dosing|treatment|treated|therapy|medication|medications|drug|drugs|"
    r"steroid|steroids|hydrocortisone|fludrocortisone|"
    r"prescribed|prescription|replace|replacement|administer"
    r")\b",
    re.IGNORECASE,
)


def clean_extracted_text(text: str) -> str:
    value = (text or "").translate(TEXT_REPLACEMENTS)
    if any(marker in value for marker in ("â", "Ã", "ï")):
        try:
            repaired = value.encode("latin-1").decode("utf-8")
        except UnicodeError:
            repaired = value
        else:
            if repaired:
                value = repaired.translate(TEXT_REPLACEMENTS)
    return value


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", clean_extracted_text(text)).strip()


def strip_unsafe_guidance(text: str) -> str:
    cleaned = clean_extracted_text(text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    safe_parts = []
    for part in parts:
        normalized_part = normalize_whitespace(part)
        if not normalized_part:
            continue
        if DOSAGE_PATTERN.search(normalized_part):
            continue
        if TREATMENT_PATTERN.search(normalized_part):
            continue
        safe_parts.append(normalized_part)
    return normalize_whitespace(" ".join(safe_parts))


def to_excerpt(text: str, *, max_length: int = 220) -> str:
    cleaned = strip_unsafe_guidance(text) or "Source excerpt omitted because it contained treatment or dosing guidance."
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
