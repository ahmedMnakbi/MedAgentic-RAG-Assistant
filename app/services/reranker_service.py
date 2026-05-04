from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings
from app.utils.text import keyword_overlap

if TYPE_CHECKING:
    from app.services.rag_service import RetrievedChunk


class RerankerService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def rerank(self, query: str, chunks: list["RetrievedChunk"], *, final_k: int) -> list["RetrievedChunk"]:
        if not chunks:
            return []
        if not self.settings.reranker_enabled:
            return chunks[:final_k]
        if self.settings.reranker_model_name == "local_keyword_overlap":
            ranked = sorted(
                chunks,
                key=lambda chunk: (keyword_overlap(query, chunk.text), -float(chunk.score)),
                reverse=True,
            )
            return ranked[:final_k]
        return self._cross_encoder_rerank(query, chunks, final_k=final_k)

    def _cross_encoder_rerank(self, query: str, chunks: list["RetrievedChunk"], *, final_k: int) -> list["RetrievedChunk"]:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            return chunks[:final_k]
        try:
            model = CrossEncoder(self.settings.reranker_model_name)
            scores = model.predict([(query, chunk.text) for chunk in chunks])
        except Exception:
            return chunks[:final_k]
        ranked = sorted(zip(scores, chunks, strict=False), key=lambda item: float(item[0]), reverse=True)
        return [chunk for _, chunk in ranked[:final_k]]
