from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.clients.vectorstore_client import VectorStoreClient
from app.core.config import Settings
from app.schemas.chat import SourceRef
from app.utils.metadata import build_source_ref
from app.utils.text import is_useful_retrieval


@dataclass(slots=True)
class RetrievedChunk:
    text: str
    metadata: dict[str, Any]
    score: float


class RagService:
    def __init__(self, settings: Settings, vectorstore_client: VectorStoreClient) -> None:
        self.settings = settings
        self.vectorstore_client = vectorstore_client

    def retrieve(
        self,
        question: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        results = self.vectorstore_client.similarity_search(
            question,
            top_k=top_k,
            document_ids=document_ids,
        )
        retrieved: list[RetrievedChunk] = []
        for document, score in results:
            text = getattr(document, "page_content", "")
            if not text:
                continue
            if not is_useful_retrieval(
                question,
                text,
                float(score),
                threshold=self.settings.retrieval_score_threshold,
            ):
                continue
            retrieved.append(
                RetrievedChunk(
                    text=text,
                    metadata=dict(getattr(document, "metadata", {}) or {}),
                    score=float(score),
                )
            )
        return retrieved

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
            parts.append(f"[Source: {filename}, page {page}]\n{chunk.text}")
        return "\n\n".join(parts)
