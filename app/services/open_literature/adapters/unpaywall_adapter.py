from __future__ import annotations

import httpx

from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class UnpaywallAdapter(ArticleSourceAdapter):
    name = "unpaywall"
    priority = 6

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        return []

    def enrich_doi(self, doi: str, *, email: str | None = None) -> ArticleCandidate | None:
        if not doi:
            return None
        params = {"email": email or "mara@example.com"}
        try:
            response = httpx.get(f"https://api.unpaywall.org/v2/{doi}", params=params, timeout=15.0)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None
        best = payload.get("best_oa_location") or {}
        return ArticleCandidate(
            title=payload.get("title") or doi,
            authors=[],
            year=str(payload.get("year") or ""),
            journal=payload.get("journal_name"),
            doi=doi,
            source=self.name,
            landing_page_url=payload.get("doi_url"),
            full_text_url=best.get("url_for_landing_page") or best.get("url"),
            pdf_url=best.get("url_for_pdf"),
            license=best.get("license"),
            is_open_access=bool(payload.get("is_oa")),
            confidence_score=0.8 if payload.get("is_oa") else 0.3,
        )

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "full_text" if candidate.full_text_url or candidate.pdf_url else "metadata_only"
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.full_text_url or candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            pdf_url=candidate.pdf_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
            warnings=[] if status == "full_text" else ["Unpaywall did not find an open full-text location."],
        )
