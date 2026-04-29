from __future__ import annotations

from pydantic import BaseModel


class DocumentRecord(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: str


class DocumentUploadResponse(DocumentRecord):
    status: str = "indexed"
