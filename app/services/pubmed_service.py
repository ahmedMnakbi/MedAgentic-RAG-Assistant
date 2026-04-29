from __future__ import annotations

import re

from app.clients.ncbi_client import NCBIClient
from app.schemas.pubmed import PubMedArticle


class PubMedService:
    def __init__(self, *, ncbi_client: NCBIClient) -> None:
        self.ncbi_client = ncbi_client

    def search(self, question: str, *, limit: int = 5) -> list[PubMedArticle]:
        query = self._normalize_query(question)
        if not query:
            return []
        return self.ncbi_client.search_pubmed(query, limit=limit)

    @staticmethod
    def _normalize_query(question: str) -> str:
        cleaned = re.sub(r"\b(pubmed|ncbi|papers|paper|studies|study|articles|article)\b", " ", question, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
