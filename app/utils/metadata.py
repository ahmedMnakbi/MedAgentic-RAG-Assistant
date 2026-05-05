from __future__ import annotations

from app.schemas.chat import SourceRef
from app.utils.text import to_excerpt


def build_source_ref(*, text: str, metadata: dict, score: float) -> SourceRef:
    page = int(metadata.get("page", 0)) + 1
    filename = str(metadata.get("filename", ""))
    chunk_id = str(metadata.get("chunk_id", ""))
    section = metadata.get("section")
    return SourceRef(
        document_id=str(metadata.get("document_id", "")),
        filename=filename,
        page=page,
        chunk_id=chunk_id,
        excerpt=to_excerpt(text),
        score=round(float(score), 4),
        section=str(section) if section else None,
        citation_label=f"{filename}, page {page}, {chunk_id}".strip(", "),
        source_status=str(metadata.get("full_text_status")) if metadata.get("full_text_status") else None,
    )
