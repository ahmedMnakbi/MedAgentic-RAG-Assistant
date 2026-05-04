from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field
from typing import Literal


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: str
    document_hash: str | None = None
    indexing_status: str = "indexed"


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
