from __future__ import annotations

from typing import Any

from app.clients.embeddings_client import EmbeddingsClient
from app.core.config import Settings
from app.core.exceptions import NotConfiguredError


class VectorStoreClient:
    def __init__(self, settings: Settings, embeddings_client: EmbeddingsClient) -> None:
        self.settings = settings
        self.embeddings_client = embeddings_client
        self._store = None

    def get_store(self):
        if self._store is None:
            try:
                from langchain_chroma import Chroma
            except ImportError as exc:
                raise NotConfiguredError("langchain-chroma is required for vector storage.") from exc

            self._store = Chroma(
                collection_name=self.settings.chroma_collection_name,
                persist_directory=str(self.settings.chroma_persist_directory),
                embedding_function=self.embeddings_client.get_embeddings(),
            )
        return self._store

    def add_documents(self, documents: list[Any]) -> None:
        if not documents:
            return
        self.get_store().add_documents(documents)

    def similarity_search(self, query: str, *, top_k: int, document_ids: list[str] | None = None):
        filters = None
        if document_ids:
            if len(document_ids) == 1:
                filters = {"document_id": document_ids[0]}
            else:
                filters = {"document_id": {"$in": document_ids}}
        return self.get_store().similarity_search_with_score(query, k=top_k, filter=filters)

    def mmr_search(self, query: str, *, top_k: int, fetch_k: int, document_ids: list[str] | None = None):
        filters = None
        if document_ids:
            if len(document_ids) == 1:
                filters = {"document_id": document_ids[0]}
            else:
                filters = {"document_id": {"$in": document_ids}}
        store = self.get_store()
        if not hasattr(store, "max_marginal_relevance_search"):
            return self.similarity_search(query, top_k=top_k, document_ids=document_ids)
        documents = store.max_marginal_relevance_search(query, k=top_k, fetch_k=fetch_k, filter=filters)
        return [(document, 0.0) for document in documents]

    def all_documents(self, *, document_ids: list[str] | None = None) -> list[Any]:
        store = self.get_store()
        if not hasattr(store, "get"):
            return []
        filters = None
        if document_ids:
            if len(document_ids) == 1:
                filters = {"document_id": document_ids[0]}
            else:
                filters = {"document_id": {"$in": document_ids}}
        payload = store.get(where=filters, include=["documents", "metadatas"])
        texts = payload.get("documents", []) or []
        metadatas = payload.get("metadatas", []) or []
        try:
            from langchain_core.documents import Document
        except ImportError:
            return []
        return [
            Document(page_content=text or "", metadata=metadata or {})
            for text, metadata in zip(texts, metadatas, strict=False)
            if text
        ]
