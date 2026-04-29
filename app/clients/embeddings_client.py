from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import NotConfiguredError


class EmbeddingsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embeddings = None

    def get_embeddings(self):
        if self._embeddings is None:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings
            except ImportError as exc:
                raise NotConfiguredError(
                    "langchain-huggingface is required to create embeddings."
                ) from exc

            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.settings.embedding_model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings
