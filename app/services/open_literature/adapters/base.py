from __future__ import annotations

from abc import ABC

from app.schemas.open_article import OpenArticleSource
from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters


class ArticleSourceAdapter(ABC):
    name: str = "base"
    priority: int = 100

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        return []

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "full_text" if candidate.full_text_url or candidate.pdf_url else "abstract_only" if candidate.abstract else "metadata_only"
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            pdf_url=candidate.pdf_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
        )

    def fetch_full_text(self, resolution: ArticleResolution) -> OpenArticleSource:
        candidate = resolution.candidate
        body_text = candidate.abstract or ""
        return OpenArticleSource(
            title=candidate.title,
            url=resolution.resolved_url or candidate.landing_page_url or "",
            source_type=self.name,
            source_name=self.name,
            source_url=resolution.resolved_url or candidate.landing_page_url,
            doi=candidate.doi,
            pmid=candidate.pmid,
            pmcid=candidate.pmcid,
            authors=candidate.authors,
            publication_date=candidate.year,
            journal=candidate.journal,
            license=resolution.license,
            abstract=candidate.abstract,
            body_text=body_text,
            extraction_quality_score=0.25 if body_text else 0.0,
            warnings=resolution.warnings,
            full_text_status=resolution.full_text_status,
            allowed_for_ai_processing=resolution.full_text_status == "full_text",
        )

    def supports(self, url_or_identifier: str) -> bool:
        return False
