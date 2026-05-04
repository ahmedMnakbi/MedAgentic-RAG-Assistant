from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.open_article import FullTextStatus, OpenArticleSource
from app.schemas.safety import SafetyAssessment

ArticleTypeFilter = Literal[
    "review",
    "clinical_trial",
    "case_report",
    "systematic_review",
    "meta_analysis",
    "guideline",
    "observational_study",
]
OpenLiteratureMode = Literal[
    "quick_answer",
    "deep_review",
    "article_digest",
    "evidence_table",
    "study_notes",
    "quiz",
    "systematic_search_lite",
]


class OpenLiteratureFilters(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    article_type: ArticleTypeFilter | None = None
    full_text_required: bool | None = None
    open_access_only: bool = True
    source_priority: list[str] = Field(default_factory=list)
    max_results: int = Field(default=10, ge=1, le=50)
    language: str | None = None


class ArticleCandidate(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    journal: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    source: str
    landing_page_url: str | None = None
    full_text_url: str | None = None
    pdf_url: str | None = None
    license: str | None = None
    is_open_access: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ArticleResolution(BaseModel):
    candidate: ArticleCandidate
    resolved_url: str | None = None
    full_text_url: str | None = None
    pdf_url: str | None = None
    pmc_xml_url: str | None = None
    source_priority: int = 100
    license: str | None = None
    full_text_status: FullTextStatus = "metadata_only"
    warnings: list[str] = Field(default_factory=list)


class EvidenceTableRow(BaseModel):
    article: str
    study_type: str | None = None
    population: str | None = None
    intervention_or_exposure: str | None = None
    outcome: str | None = None
    main_finding: str
    source_status: FullTextStatus
    citation: str


class OpenLiteratureSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    filters: OpenLiteratureFilters = Field(default_factory=OpenLiteratureFilters)
    output_mode: OpenLiteratureMode = "quick_answer"


class OpenLiteratureSearchResponse(BaseModel):
    status: Literal["ok", "no_source", "refused"]
    query: str
    search_strategy: list[str] = Field(default_factory=list)
    query_variants: list[str] = Field(default_factory=list)
    sources_searched: list[str] = Field(default_factory=list)
    candidates: list[ArticleCandidate] = Field(default_factory=list)
    resolutions: list[ArticleResolution] = Field(default_factory=list)
    selected_sources: list[OpenArticleSource] = Field(default_factory=list)
    answer: str | None = None
    evidence_table: list[EvidenceTableRow] = Field(default_factory=list)
    safety: SafetyAssessment | None = None
    warnings: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    full_text_count: int = 0
    abstract_only_count: int = 0
    metadata_only_count: int = 0
    restricted_count: int = 0


class OpenLiteratureTransformRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4000)
    pmids: list[str] = Field(default_factory=list, max_length=8)
    action: OpenLiteratureMode = "quick_answer"
    full_text_required: bool | None = None
