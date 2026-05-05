from __future__ import annotations

import re

from app.schemas.open_literature import ArticleCandidate


class LiteratureDeduplicationService:
    def deduplicate(self, candidates: list[ArticleCandidate]) -> list[ArticleCandidate]:
        merged: dict[str, ArticleCandidate] = {}
        for candidate in candidates:
            key = self._key(candidate)
            existing = merged.get(key)
            if not existing:
                merged[key] = candidate
                continue
            merged[key] = self._prefer(existing, candidate)
        return sorted(merged.values(), key=lambda item: item.confidence_score, reverse=True)

    @staticmethod
    def _key(candidate: ArticleCandidate) -> str:
        for value in (candidate.doi, candidate.pmid, candidate.pmcid):
            if value:
                return value.lower()
        return re.sub(r"[^a-z0-9]+", " ", candidate.title.lower()).strip()

    @staticmethod
    def _prefer(left: ArticleCandidate, right: ArticleCandidate) -> ArticleCandidate:
        left_full = bool(left.full_text_url or left.pdf_url or left.pmcid)
        right_full = bool(right.full_text_url or right.pdf_url or right.pmcid)
        if right_full and not left_full:
            winner, loser = right, left
        elif left_full and not right_full:
            winner, loser = left, right
        else:
            winner, loser = (right, left) if right.confidence_score > left.confidence_score else (left, right)
        winner.abstract = winner.abstract or loser.abstract
        winner.doi = winner.doi or loser.doi
        winner.pmid = winner.pmid or loser.pmid
        winner.pmcid = winner.pmcid or loser.pmcid
        winner.full_text_url = winner.full_text_url or loser.full_text_url
        winner.pdf_url = winner.pdf_url or loser.pdf_url
        winner.license = winner.license or loser.license
        winner.is_open_access = winner.is_open_access or loser.is_open_access
        return winner
