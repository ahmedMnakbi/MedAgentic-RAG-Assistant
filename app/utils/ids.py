from __future__ import annotations

from uuid import uuid4


def generate_document_id() -> str:
    return f"doc_{uuid4().hex}"
