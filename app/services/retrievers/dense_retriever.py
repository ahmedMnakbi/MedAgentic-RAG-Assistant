from __future__ import annotations

from typing import TYPE_CHECKING

from app.clients.vectorstore_client import VectorStoreClient
from app.services.retrievers.base import BaseRetriever

if TYPE_CHECKING:
    from app.services.rag_service import RetrievedChunk


class DenseRetriever(BaseRetriever):
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

        results = self.vectorstore_client.similarity_search(
            query,
            top_k=top_k,
            document_ids=document_ids,
        )
        return [
            RetrievedChunk(
                text=getattr(document, "page_content", ""),
                metadata=dict(getattr(document, "metadata", {}) or {}),
                score=float(score),
            )
            for document, score in results
            if getattr(document, "page_content", "")
        ]

    def retrieve_mmr(
        self,
        query: str,
        *,
        top_k: int,
        fetch_k: int,
        document_ids: list[str] | None = None,
    ) -> list["RetrievedChunk"]:
        from app.services.rag_service import RetrievedChunk

        results = self.vectorstore_client.mmr_search(
            query,
            top_k=top_k,
            fetch_k=fetch_k,
            document_ids=document_ids,
        )
        return [
            RetrievedChunk(
                text=getattr(document, "page_content", ""),
                metadata=dict(getattr(document, "metadata", {}) or {}),
                score=float(score),
            )
            for document, score in results
            if getattr(document, "page_content", "")
        ]
