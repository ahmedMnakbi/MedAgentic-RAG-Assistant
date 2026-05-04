from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

from app.clients.vectorstore_client import VectorStoreClient
from app.services.retrievers.base import BaseRetriever
from app.utils.text import normalize_whitespace

if TYPE_CHECKING:
    from app.services.rag_service import RetrievedChunk


class BM25Retriever(BaseRetriever):
    def __init__(self, vectorstore_client: VectorStoreClient) -> None:
        self.vectorstore_client = vectorstore_client

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        fetch_k: int,
        document_ids: list[str] | None = None,
    ) -> list["RetrievedChunk"]:
        from app.services.rag_service import RetrievedChunk

        documents = self.vectorstore_client.all_documents(document_ids=document_ids)
        if not documents:
            return []
        query_terms = self._tokens(query)
        if not query_terms:
            return []

        tokenized = [self._tokens(getattr(document, "page_content", "")) for document in documents]
        doc_freq: Counter[str] = Counter()
        for terms in tokenized:
            doc_freq.update(set(terms))
        avg_len = sum(len(terms) for terms in tokenized) / max(1, len(tokenized))
        scored = []
        for document, terms in zip(documents, tokenized, strict=False):
            score = self._score(query_terms, terms, doc_freq, len(documents), avg_len)
            if score <= 0:
                continue
            scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(
                text=getattr(document, "page_content", ""),
                metadata=dict(getattr(document, "metadata", {}) or {}),
                score=round(1.0 / (score + 1.0), 6),
            )
            for score, document in scored[:top_k]
        ]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9]{3,}", normalize_whitespace(text).lower())

    @staticmethod
    def _score(
        query_terms: list[str],
        doc_terms: list[str],
        doc_freq: Counter[str],
        doc_count: int,
        avg_len: float,
    ) -> float:
        if not doc_terms:
            return 0.0
        counts = Counter(doc_terms)
        score = 0.0
        k1 = 1.5
        b = 0.75
        doc_len = len(doc_terms)
        for term in query_terms:
            if term not in counts:
                continue
            idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            tf = counts[term]
            denom = tf + k1 * (1 - b + b * doc_len / max(avg_len, 1.0))
            score += idf * ((tf * (k1 + 1)) / denom)
        return score
