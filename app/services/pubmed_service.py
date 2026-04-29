from __future__ import annotations

import re

from app.clients.ncbi_client import NCBIClient
from app.schemas.pubmed import PubMedArticle

PROMPT_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
NON_TOPIC_PLACEHOLDER_KEYS = {
    "audience",
    "format",
    "style",
    "tone",
    "length",
    "output",
    "goal",
}


class PubMedService:
    def __init__(self, *, ncbi_client: NCBIClient) -> None:
        self.ncbi_client = ncbi_client

    def search(self, question: str, *, limit: int = 5) -> list[PubMedArticle]:
        topic = self._normalize_query(question)
        if not topic:
            return []
        primary_query = self._build_search_query(topic)
        articles = self.ncbi_client.search_pubmed(primary_query, limit=limit)
        if articles:
            return articles
        if primary_query != topic:
            return self.ncbi_client.search_pubmed(topic, limit=limit)
        return []

    @staticmethod
    def _normalize_query(question: str) -> str:
        cleaned = PubMedService._replace_prompt_placeholders(question.strip())
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
        cleaned = re.sub(
            r",?\s*(providing|with|including)\s+.+?(?=[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        topic_match = re.search(
            r"\b(?:on|about|regarding)\s+(.+?)(?=\s+from\b|,\s*|[.?!;]|$)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if topic_match:
            cleaned = topic_match.group(1)

        cleaned = re.sub(
            r"\b("
            r"pubmed|ncbi|papers|paper|studies|study|articles|article|"
            r"provide|list|relevant|find|show|give|return|search|results?|"
            r"please|me|metadata|educational|content|medical|overview|bullet|format|"
            r"key|points|caveats"
            r")\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9)']+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+,", ",", cleaned).strip(" ,")
        return cleaned

    @staticmethod
    def _build_search_query(topic: str) -> str:
        cleaned_topic = re.sub(r"\s+", " ", topic).strip()
        if not cleaned_topic:
            return ""
        escaped_topic = cleaned_topic.replace('"', "")
        return f"(\"{escaped_topic}\"[Title/Abstract] OR \"{escaped_topic}\"[MeSH Terms] OR {escaped_topic})"

    @staticmethod
    def _replace_prompt_placeholders(question: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            inner = match.group(1).strip()
            if ":" not in inner:
                return inner
            key, value = inner.split(":", 1)
            if key.strip().lower() in NON_TOPIC_PLACEHOLDER_KEYS:
                return " "
            return value.strip()

        return PROMPT_PLACEHOLDER_PATTERN.sub(_replace, question)
