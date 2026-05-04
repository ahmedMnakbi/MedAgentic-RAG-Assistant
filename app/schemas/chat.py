from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import QuizItem
from app.schemas.pubmed import PubMedArticle
from app.schemas.safety import SafetyAssessment

ChatMode = Literal["auto", "rag", "summarize", "simplify", "quiz", "pubmed", "prompt_enhance"]
ResponseMode = Literal[
    "refuse",
    "rag",
    "summarize",
    "simplify",
    "quiz",
    "pubmed",
    "prompt_enhance",
]
ChatStatus = Literal["ok", "refused", "no_source"]


class SourceRef(BaseModel):
    document_id: str
    filename: str
    page: int
    chunk_id: str
    excerpt: str
    score: float
    section: str | None = None
    citation_label: str | None = None
    source_status: str | None = None

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    mode: ChatMode = "auto"
    document_ids: list[str] | None = None
    enhance_prompt: bool = False
    top_k: int = Field(default=4, ge=1, le=10)


class AskResponse(BaseModel):
    status: ChatStatus
    mode_used: ResponseMode
    answer: str
    safety: SafetyAssessment
    sources: list[SourceRef] = Field(default_factory=list)
    enhanced_prompt: str | None = None
    quiz_items: list[QuizItem] | None = None
    pubmed_results: list[PubMedArticle] | None = None
    warnings: list[str] = Field(default_factory=list)
