from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FullTextStatus = Literal[
    "full_text",
    "abstract_only",
    "metadata_only",
    "restricted",
    "extraction_failed",
]
OpenArticleAction = Literal[
    "summarize",
    "simplify",
    "quiz",
    "compare",
    "extract_key_claims",
    "extract_limitations",
    "extract_pico",
    "citation_card",
    "study_notes",
    "exam_questions",
    "extract_methodology",
]


class ArticleSection(BaseModel):
    title: str
    text: str


class OpenArticleSource(BaseModel):
    title: str
    url: str
    source_type: str = "generic_html"
    source_name: str | None = None
    source_url: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_date: str | None = None
    journal: str | None = None
    license: str | None = None
    abstract: str | None = None
    body_text: str = ""
    sections: list[ArticleSection] = Field(default_factory=list)
    tables_text: str = ""
    figures_captions: str = ""
    references: list[str] = Field(default_factory=list)
    extraction_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    full_text_status: FullTextStatus = "extraction_failed"
    allowed_for_ai_processing: bool = False


class OpenArticleImportRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


class OpenArticleImportResponse(BaseModel):
    status: Literal["ok", "no_source", "restricted"]
    article: OpenArticleSource | None = None
    warnings: list[str] = Field(default_factory=list)


class OpenArticleTransformRequest(BaseModel):
    url: str | None = Field(default=None, min_length=10, max_length=2000)
    article: OpenArticleSource | None = None
    action: OpenArticleAction = "summarize"
    question: str | None = Field(default=None, min_length=3, max_length=4000)
    enhance_prompt: bool = False


class OpenArticleTransformResponse(BaseModel):
    status: Literal["ok", "refused", "no_source", "restricted"]
    action: OpenArticleAction
    answer: str
    article: OpenArticleSource | None = None
    quiz_items: list[dict] | None = None
    warnings: list[str] = Field(default_factory=list)
