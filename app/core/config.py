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

    app_name: str = "MARA"
    app_env: str = "development"
    app_debug: bool = False
    api_prefix: str = "/api"

    groq_api_key: SecretStr | None = None
    groq_model: str | None = None
    groq_model_answer: str | None = None
    groq_model_prompt_enhancer: str | None = None
    groq_model_router: str | None = None
    groq_model_safety: str | None = None

    embedding_provider: str = "huggingface"
    embedding_model_name: str = DEFAULT_EMBEDDING_MODEL
    chroma_collection_name: str = DEFAULT_COLLECTION_NAME

    upload_dir: Path = Field(default_factory=lambda: BASE_DIR / "app" / "storage" / "uploads")
    chroma_persist_directory: Path = Field(
        default_factory=lambda: BASE_DIR / "app" / "storage" / "chroma"
    )
    documents_registry_file: Path = Field(
        default_factory=lambda: BASE_DIR / "app" / "storage" / "documents.json"
    )

    max_upload_size_mb: int = 100
    retrieval_default_top_k: int = 4
    retrieval_strategy: str = "similarity"
    retrieval_fetch_k: int = 20
    retrieval_final_k: int = 4
    retrieval_score_threshold: float = 1.35
    chunk_size: int = 1000
    chunk_overlap: int = 150
    context_max_chars: int = 12000
    reranker_enabled: bool = False
    reranker_model_name: str = "local_keyword_overlap"

    enable_langgraph_rag: bool = False
    enable_open_literature_engine: bool = True
    enable_open_article_pipeline: bool = True
    enable_prompt_enhancer_v2: bool = True
    enable_post_safety_check: bool = True
    enable_grounding_check: bool = True

    open_literature_max_candidates: int = 12
    open_literature_require_full_text_default: bool = False
    open_literature_allowed_sources: str = ""
    open_literature_blocked_domains: str = "localhost,127.0.0.1,::1"
    open_literature_enable_generic_html: bool = True
    open_literature_enable_cureus_experimental: bool = False

    ncbi_email: str | None = None
    ncbi_tool: str = "MARA"
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
