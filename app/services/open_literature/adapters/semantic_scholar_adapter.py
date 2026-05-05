from __future__ import annotations

from app.services.open_literature.adapters.base import ArticleSourceAdapter


class SemanticScholarAdapter(ArticleSourceAdapter):
    name = "semantic_scholar"
    priority = 9
