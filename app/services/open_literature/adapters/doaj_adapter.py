from __future__ import annotations

from app.services.open_literature.adapters.base import ArticleSourceAdapter


class DOAJAdapter(ArticleSourceAdapter):
    name = "doaj"
    priority = 10
