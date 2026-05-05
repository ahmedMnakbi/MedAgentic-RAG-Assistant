from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.rag_service import RetrievedChunk


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        *,
        top_k: int,
        fetch_k: int,
        document_ids: list[str] | None = None,
    ) -> list["RetrievedChunk"]:
        raise NotImplementedError
