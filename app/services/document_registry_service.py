from __future__ import annotations

import json
from json import JSONDecodeError
from threading import Lock

from app.core.config import Settings
from app.core.exceptions import ExternalServiceError
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

    def remove_document(self, document_id: str) -> DocumentRecord | None:
        with self._lock:
            payload = self._read()
            documents = payload.setdefault("documents", [])
            removed: DocumentRecord | None = None
            kept = []
            for item in documents:
                document = DocumentRecord.model_validate(item)
                if document.document_id == document_id:
                    removed = document
                else:
                    kept.append(document.model_dump())
            if removed:
                payload["documents"] = kept
                self._write(payload)
            return removed

    def find_by_hash(self, document_hash: str) -> DocumentRecord | None:
        if not document_hash:
            return None
        for document in self.list_documents():
            if document.document_hash == document_hash:
                return document
        return None

    def _read(self) -> dict:
        if not self.settings.documents_registry_file.exists():
            return {"documents": []}
        raw = self.settings.documents_registry_file.read_text(encoding="utf-8-sig").strip() or '{"documents": []}'
        try:
            return json.loads(raw)
        except JSONDecodeError as exc:
            raise ExternalServiceError(
                "Document registry could not be read. Existing PDF files were left unchanged."
            ) from exc

    def _write(self, payload: dict) -> None:
        self.settings.documents_registry_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
