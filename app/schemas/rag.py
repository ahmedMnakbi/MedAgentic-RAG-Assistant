from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalStrategy = Literal["similarity", "mmr", "hybrid", "hybrid_rerank"]


class RetrievalSettings(BaseModel):
    strategy: RetrievalStrategy = "similarity"
    top_k: int = Field(default=4, ge=1, le=20)
    fetch_k: int = Field(default=20, ge=1, le=50)
    score_threshold: float | None = None


class PackedContext(BaseModel):
    text: str
    source_labels: list[str] = Field(default_factory=list)
    omitted_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class GroundingResult(BaseModel):
    grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    warning: str | None = None
