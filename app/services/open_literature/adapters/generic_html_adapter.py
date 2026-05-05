from __future__ import annotations

from app.schemas.open_article import OpenArticleSource
from app.schemas.open_literature import ArticleCandidate, ArticleResolution
from app.services.open_article_service import OpenArticleService
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class GenericOAHTMLAdapter(ArticleSourceAdapter):
    name = "generic_html"
    priority = 50

    def __init__(self, open_article_service: OpenArticleService) -> None:
        self.open_article_service = open_article_service

    def supports(self, url_or_identifier: str) -> bool:
        return url_or_identifier.startswith(("http://", "https://"))

    def fetch_full_text(self, resolution: ArticleResolution) -> OpenArticleSource:
        url = resolution.full_text_url or resolution.resolved_url or resolution.candidate.landing_page_url
        if not url:
            return super().fetch_full_text(resolution)
        article = self.open_article_service.import_url(url)
        if len(article.body_text) < 250 or article.extraction_quality_score < 0.2:
            article.full_text_status = "extraction_failed"
            article.allowed_for_ai_processing = False
            article.warnings.append("Generic HTML parser rejected the page because extraction was too short or low quality.")
        return article

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.full_text_url or candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status="full_text" if candidate.full_text_url or candidate.landing_page_url else "metadata_only",
            warnings=["Generic HTML extraction is a fallback and may be partial."],
        )
