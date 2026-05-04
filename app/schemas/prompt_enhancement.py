from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PromptTargetMode = Literal[
    "auto",
    "general_education",
    "rag",
    "document_rag",
    "summarize",
    "simplify",
    "quiz",
    "pubmed",
    "pubmed_metadata",
    "open_literature",
    "open_article",
    "prompt_enhance",
]
PromptSourceScope = Literal[
    "uploaded_documents",
    "pubmed",
    "open_literature",
    "open_article",
    "both",
    "none",
    "auto",
]
PromptOutputFormatV2 = Literal[
    "markdown",
    "table",
    "json",
    "quiz_json",
    "study_notes",
    "deep_review",
    "article_digest",
    "evidence_table",
]


class PromptEnhanceV2Request(BaseModel):
    raw_input: str = Field(min_length=3, max_length=8000)
    target_mode: PromptTargetMode = "auto"
    audience: str | None = Field(default=None, max_length=300)
    source_scope: PromptSourceScope = "auto"
    output_format: PromptOutputFormatV2 = "markdown"
    strict_grounding: bool = True
    include_retrieval_plan: bool = True
    include_safety_checks: bool = True
    full_text_required: bool | None = None


class PromptEnhanceV2Response(BaseModel):
    original_input: str
    intent_summary: str
    inferred_mode: str
    optimized_prompt: str
    rag_query: str | None = None
    pubmed_query: str | None = None
    open_literature_query: str | None = None
    open_article_instruction: str | None = None
    context_plan: list[str] = Field(default_factory=list)
    retrieval_plan: list[str] = Field(default_factory=list)
    output_contract: list[str] = Field(default_factory=list)
    safety_plan: list[str] = Field(default_factory=list)
    quality_checks: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    can_send_to_assistant: bool = True
