from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import QuizItem
from app.schemas.safety import SafetyAssessment

PubMedContentAvailability = Literal["metadata_only", "abstract_only", "pmc_full_text"]
PubMedAction = Literal["summarize", "simplify", "quiz", "compare"]
PubMedResponseStatus = Literal["ok", "refused", "no_source"]
PubMedSourceType = Literal["abstract_only", "pmc_full_text", "open_access_url"]


class PubMedArticle(BaseModel):
    pmid: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str
    publication_date: str
    pubmed_url: str
    pmcid: str | None = None
    full_text_url: str | None = None
    content_availability: PubMedContentAvailability = "metadata_only"


class PubMedSelectedSource(BaseModel):
    title: str
    excerpt: str
    source_type: PubMedSourceType
    source_url: str
    pmid: str | None = None
    pmcid: str | None = None


class PubMedTransformRequest(BaseModel):
    pmids: list[str] = Field(min_length=1, max_length=5)
    action: PubMedAction
    question: str | None = Field(default=None, min_length=3, max_length=4000)
    enhance_prompt: bool = False
    prefer_full_text: bool = True


class PubMedUrlTransformRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)
    action: PubMedAction
    question: str | None = Field(default=None, min_length=3, max_length=4000)
    enhance_prompt: bool = False


class PubMedTransformResponse(BaseModel):
    status: PubMedResponseStatus
    action: PubMedAction
    answer: str
    safety: SafetyAssessment
    selected_sources: list[PubMedSelectedSource] = Field(default_factory=list)
    enhanced_prompt: str | None = None
    quiz_items: list[QuizItem] | None = None
    warnings: list[str] = Field(default_factory=list)
