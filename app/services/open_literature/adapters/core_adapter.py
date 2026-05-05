from __future__ import annotations

from app.services.open_literature.adapters.base import ArticleSourceAdapter


class COREAdapter(ArticleSourceAdapter):
    name = "core"
    priority = 8
