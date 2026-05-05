from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.clients.vectorstore_client import VectorStoreClient
from app.core.config import Settings
from app.schemas.chat import SourceRef
from app.schemas.rag import PackedContext
from app.services.context_packer_service import ContextPackerService
from app.services.reranker_service import RerankerService
from app.services.retrievers.bm25_retriever import BM25Retriever
from app.services.retrievers.dense_retriever import DenseRetriever
from app.services.retrievers.hybrid_retriever import HybridRetriever
from app.utils.metadata import build_source_ref
from app.utils.text import is_useful_retrieval, strip_unsafe_guidance


@dataclass(slots=True)
class RetrievedChunk:
    text: str
    metadata: dict[str, Any]
    score: float


class RagService:
    def __init__(self, settings: Settings, vectorstore_client: VectorStoreClient) -> None:
        self.settings = settings
        self.vectorstore_client = vectorstore_client
        self.dense_retriever = DenseRetriever(vectorstore_client)
        self.bm25_retriever = BM25Retriever(vectorstore_client)
        self.hybrid_retriever = HybridRetriever(self.dense_retriever, self.bm25_retriever)
        self.reranker_service = RerankerService(settings)
        self.context_packer_service = ContextPackerService(settings)

    def retrieve(
        self,
        question: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        strategy = self._strategy()
        fetch_k = max(top_k, self.settings.retrieval_fetch_k)
        final_k = min(top_k or self.settings.retrieval_final_k, self.settings.retrieval_final_k or top_k)
        if strategy == "mmr":
            raw_retrieved = self.dense_retriever.retrieve_mmr(
                question,
                top_k=final_k,
                fetch_k=fetch_k,
                document_ids=document_ids,
            )
        elif strategy in {"hybrid", "hybrid_rerank"}:
            raw_retrieved = self.hybrid_retriever.retrieve(
                question,
                top_k=fetch_k if strategy == "hybrid_rerank" else final_k,
                fetch_k=fetch_k,
                document_ids=document_ids,
            )
        else:
            raw_retrieved = self.dense_retriever.retrieve(
                question,
                top_k=final_k,
                fetch_k=fetch_k,
                document_ids=document_ids,
            )
        retrieved: list[RetrievedChunk] = []
        for chunk in raw_retrieved:
            if not chunk.text:
                continue
            if not is_useful_retrieval(
                question,
                chunk.text,
                float(chunk.score),
                threshold=self.settings.retrieval_score_threshold,
            ):
                continue
            retrieved.append(chunk)
        if strategy == "hybrid_rerank":
            return self.reranker_service.rerank(question, retrieved, final_k=final_k)
        return retrieved[:final_k]

    def to_source_refs(self, chunks: list[RetrievedChunk]) -> list[SourceRef]:
        return [
            build_source_ref(text=chunk.text, metadata=chunk.metadata, score=chunk.score)
            for chunk in chunks
        ]

    @staticmethod
    def build_context(chunks: list[RetrievedChunk]) -> str:
        parts = []
        for chunk in chunks:
            filename = chunk.metadata.get("filename", "document")
            page = int(chunk.metadata.get("page", 0)) + 1
            safe_text = strip_unsafe_guidance(chunk.text)
            if not safe_text:
                continue
            parts.append(f"[Source: {filename}, page {page}]\n{safe_text}")
        return "\n\n".join(parts)

    def pack_context(self, chunks: list[RetrievedChunk]) -> PackedContext:
        return self.context_packer_service.pack(chunks)

    def retrieve_document_chunks(
        self,
        *,
        document_ids: list[str] | None = None,
        page_from: int | None = None,
        page_to: int | None = None,
    ) -> list[RetrievedChunk]:
        documents = self.vectorstore_client.all_documents(document_ids=document_ids)
        chunks: list[RetrievedChunk] = []
        for document in documents:
            metadata = dict(getattr(document, "metadata", {}) or {})
            page = int(metadata.get("page", 0) or 0) + 1
            if page_from is not None and page < page_from:
                continue
            if page_to is not None and page > page_to:
                continue
            chunks.append(
                RetrievedChunk(
                    text=getattr(document, "page_content", ""),
                    metadata=metadata,
                    score=0.0,
                )
            )
        return sorted(
            chunks,
            key=lambda chunk: (
                str(chunk.metadata.get("document_id", "")),
                int(chunk.metadata.get("page", 0) or 0),
                str(chunk.metadata.get("chunk_id", "")),
            ),
        )

    def _strategy(self) -> str:
        strategy = (self.settings.retrieval_strategy or "similarity").lower()
        if strategy not in {"similarity", "mmr", "hybrid", "hybrid_rerank"}:
            return "similarity"
        return strategy
