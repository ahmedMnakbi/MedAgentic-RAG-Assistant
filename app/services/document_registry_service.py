from __future__ import annotations

import json
from threading import Lock

from app.core.config import Settings
from app.schemas.documents import DocumentRecord


class DocumentRegistryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = Lock()
        self.settings.ensure_storage_paths()

    def list_documents(self) -> list[DocumentRecord]:
        payload = self._read()
        documents = [DocumentRecord.model_validate(item) for item in payload.get("documents", [])]
        return sorted(documents, key=lambda item: item.uploaded_at, reverse=True)

    def save_document(self, document: DocumentRecord) -> None:
        with self._lock:
            payload = self._read()
            documents = payload.setdefault("documents", [])
            documents.append(document.model_dump())
            self._write(payload)

    def _read(self) -> dict:
        if not self.settings.documents_registry_file.exists():
            return {"documents": []}
        raw = self.settings.documents_registry_file.read_text(encoding="utf-8").strip() or '{"documents": []}'
        return json.loads(raw)

    def _write(self, payload: dict) -> None:
        self.settings.documents_registry_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
