from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field
from typing import Literal

DocumentScopeCategory = Literal["medical", "medical_adjacent", "non_medical", "unknown"]


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: str
    document_hash: str | None = None
    indexing_status: str = "indexed"
    scope_category: DocumentScopeCategory = "unknown"
    scope_confidence: float = 0.0
    scope_reason: str = "Scope was not classified for this document."
    eligible_for_medical_workflows: bool = True


class DocumentUploadResponse(DocumentRecord):
    status: str = "indexed"


class DocumentDeleteResponse(BaseModel):
    status: str = "deleted"
    document_id: str
    warnings: list[str] = Field(default_factory=list)


DocumentWorkflowAction = Literal[
    "summary",
    "page_range_summary",
    "simplification",
    "quiz",
    "key_concepts",
]


class DocumentWorkflowRequest(BaseModel):
    action: DocumentWorkflowAction
    document_ids: list[str] | None = None
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)
    question: str | None = Field(default=None, min_length=3, max_length=4000)


class DocumentWorkflowResponse(BaseModel):
    status: Literal["ok", "no_source", "refused"]
    action: DocumentWorkflowAction
    answer: str
    warnings: list[str] = Field(default_factory=list)
    source_count: int = 0
    quiz_items: list[dict] | None = None
