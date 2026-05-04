from __future__ import annotations

from app.schemas.open_literature import ArticleCandidate, ArticleResolution
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class CureusAdapter(ArticleSourceAdapter):
    name = "cureus"
    priority = 80

    def supports(self, url_or_identifier: str) -> bool:
        return "cureus.com" in url_or_identifier.lower()

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.landing_page_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status="restricted",
            warnings=[
                "Cureus is treated as link-only/restricted by default; prefer a PMC Open Access version when available."
            ],
        )
