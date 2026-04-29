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
        cleaned = question.strip()
        cleaned = re.sub(
            r",?\s*(excluding|without)\s+.+?(?=,\s*(and\s+)?focusing\b|[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r",?\s*(and\s+)?focusing\s+on\s+.+?(?=[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        topic_match = re.search(r"\b(?:on|about|regarding)\s+(.+)$", cleaned, flags=re.IGNORECASE)
        if topic_match:
            cleaned = topic_match.group(1)

        cleaned = re.sub(
            r"\b("
            r"pubmed|ncbi|papers|paper|studies|study|articles|article|"
            r"provide|list|relevant|find|show|give|return|search|results?|"
            r"please|me|metadata|educational|content"
            r")\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9)']+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+,", ",", cleaned).strip(" ,")
        return cleaned
