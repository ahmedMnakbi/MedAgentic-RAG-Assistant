from __future__ import annotations

from app.schemas.open_article import OpenArticleSource


class ExtractionQualityService:
    def score(self, source: OpenArticleSource) -> float:
        if source.full_text_status != "full_text":
            return source.extraction_quality_score
        length_score = min(len(source.body_text) / 6000, 1.0)
        section_score = min(len(source.sections) / 6, 1.0)
        return round(max(source.extraction_quality_score, length_score * 0.7 + section_score * 0.3), 3)
