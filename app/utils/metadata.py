from __future__ import annotations

from app.schemas.chat import SourceRef
from app.utils.text import to_excerpt


def build_source_ref(*, text: str, metadata: dict, score: float) -> SourceRef:
    return SourceRef(
        document_id=str(metadata.get("document_id", "")),
        filename=str(metadata.get("filename", "")),
        page=int(metadata.get("page", 0)) + 1,
        chunk_id=str(metadata.get("chunk_id", "")),
        excerpt=to_excerpt(text),
        score=round(float(score), 4),
    )
