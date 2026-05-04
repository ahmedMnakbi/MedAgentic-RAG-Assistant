from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.retrievers.base import BaseRetriever
from app.services.retrievers.bm25_retriever import BM25Retriever
from app.services.retrievers.dense_retriever import DenseRetriever

if TYPE_CHECKING:
    from app.services.rag_service import RetrievedChunk


class HybridRetriever(BaseRetriever):
    def __init__(self, dense_retriever: DenseRetriever, bm25_retriever: BM25Retriever) -> None:
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever

    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        fetch_k: int,
        document_ids: list[str] | None = None,
    ) -> list["RetrievedChunk"]:
        dense = self.dense_retriever.retrieve(
            query,
            top_k=fetch_k,
            fetch_k=fetch_k,
            document_ids=document_ids,
        )
        sparse = self.bm25_retriever.retrieve(
            query,
            top_k=fetch_k,
            fetch_k=fetch_k,
            document_ids=document_ids,
        )
        return self._rrf(dense, sparse)[:top_k]

    @staticmethod
    def _key(chunk: "RetrievedChunk") -> str:
        chunk_id = chunk.metadata.get("chunk_id")
        if chunk_id:
            return str(chunk_id)
        return f"{chunk.metadata.get('document_id')}::{chunk.metadata.get('page')}::{chunk.text[:80]}"

    def _rrf(self, dense: list["RetrievedChunk"], sparse: list["RetrievedChunk"]) -> list["RetrievedChunk"]:
        scores: dict[str, float] = {}
        chunks: dict[str, "RetrievedChunk"] = {}
        rank_constant = 60
        for result_set in (dense, sparse):
            for rank, chunk in enumerate(result_set, start=1):
                key = self._key(chunk)
                chunks.setdefault(key, chunk)
                scores[key] = scores.get(key, 0.0) + 1.0 / (rank_constant + rank)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        fused = []
        for key, score in ordered:
            chunk = chunks[key]
            chunk.score = round(1.0 / (score + 1.0), 6)
            fused.append(chunk)
        return fused
