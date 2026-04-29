from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import DEFAULT_COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MedAgentic RAG Assistant"
    app_env: str = "development"
    app_debug: bool = False
    api_prefix: str = "/api"

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None

    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL
    chroma_collection_name: str = DEFAULT_COLLECTION_NAME

    upload_dir: Path = Field(default_factory=lambda: BASE_DIR / "app" / "storage" / "uploads")
    chroma_persist_directory: Path = Field(
        default_factory=lambda: BASE_DIR / "app" / "storage" / "chroma"
    )
    documents_registry_file: Path = Field(
        default_factory=lambda: BASE_DIR / "app" / "storage" / "documents.json"
    )

    max_upload_size_mb: int = 20
    retrieval_default_top_k: int = 4
    retrieval_score_threshold: float = 1.35

    ncbi_email: str | None = None
    ncbi_tool: str = "MedAgenticRAGAssistant"
    ncbi_api_key: SecretStr | None = None
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_storage_paths(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
        self.documents_registry_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.documents_registry_file.exists():
            self.documents_registry_file.write_text('{"documents": []}', encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage_paths()
    return settings
