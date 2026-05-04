from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.clients.pdf_loader import PDFLoaderClient
from app.clients.vectorstore_client import VectorStoreClient
from app.core.config import Settings
from app.core.exceptions import EmptyPdfError, ExternalServiceError, InvalidPdfError
from app.schemas.documents import DocumentRecord, DocumentUploadResponse
from app.services.rag_service import RetrievedChunk
from app.services.document_registry_service import DocumentRegistryService
from app.utils.file_validation import validate_pdf_upload
from app.utils.ids import generate_document_id
from app.utils.text import normalize_whitespace


class DocumentService:
    def __init__(
        self,
        *,
        settings: Settings,
        pdf_loader: PDFLoaderClient,
        vectorstore_client: VectorStoreClient,
        registry_service: DocumentRegistryService,
    ) -> None:
        self.settings = settings
        self.pdf_loader = pdf_loader
        self.vectorstore_client = vectorstore_client
        self.registry_service = registry_service

    def list_documents(self) -> list[DocumentRecord]:
        return self.registry_service.list_documents()

    def process_upload(
        self,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentUploadResponse:
        validate_pdf_upload(
            filename=filename,
            content_type=content_type,
            content=content,
            max_bytes=self.settings.max_upload_size_bytes,
        )

        document_hash = hashlib.sha256(content).hexdigest()
        existing = self.registry_service.find_by_hash(document_hash)
        if existing:
            return DocumentUploadResponse(**existing.model_dump(), status="duplicate")

        document_id = generate_document_id()
        target_path = self.settings.upload_dir / f"{document_id}.pdf"
        target_path.write_bytes(content)

        try:
            pages = self.pdf_loader.load_pages(target_path)
        except Exception as exc:
            target_path.unlink(missing_ok=True)
            raise InvalidPdfError() from exc

        total_pages = len(pages)
        prepared_pages = self._prepare_pages(
            pages,
            document_id=document_id,
            filename=filename,
            document_hash=document_hash,
        )
        if not prepared_pages:
            target_path.unlink(missing_ok=True)
            raise EmptyPdfError()

        try:
            chunked_documents = self._chunk_pages(prepared_pages)
            self._sanitize_document_metadata(chunked_documents)
        except Exception as exc:
            target_path.unlink(missing_ok=True)
            raise ExternalServiceError(
                "Document indexing failed while preparing searchable chunks. "
                "The PDF text was readable, but the chunking step rejected it."
            ) from exc
        vector_indexed = True
        try:
            self.vectorstore_client.add_documents(chunked_documents)
        except Exception:
            vector_indexed = False

        uploaded_at = datetime.now(UTC).isoformat()
        record = DocumentRecord(
            document_id=document_id,
            filename=filename,
            page_count=total_pages,
            chunk_count=len(chunked_documents),
            uploaded_at=uploaded_at,
            document_hash=document_hash,
        )
        try:
            self.registry_service.save_document(record)
        except Exception as exc:
            target_path.unlink(missing_ok=True)
            raise ExternalServiceError("Document metadata could not be written to the registry.") from exc
        return DocumentUploadResponse(
            **record.model_dump(),
            status="indexed" if vector_indexed else "indexed_text_only",
        )

    def load_stored_document_chunks(
        self,
        *,
        document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        records = self.list_documents()
        selected_ids = set(document_ids or [])
        selected_records = [record for record in records if not selected_ids or record.document_id in selected_ids]
        chunks: list[RetrievedChunk] = []
        for record in selected_records:
            file_path = self.settings.upload_dir / f"{record.document_id}.pdf"
            if not file_path.exists():
                continue
            try:
                pages = self.pdf_loader.load_pages(file_path)
                prepared_pages = self._prepare_pages(
                    pages,
                    document_id=record.document_id,
                    filename=record.filename,
                    document_hash=record.document_hash or "",
                )
                chunked_documents = self._chunk_pages(prepared_pages)
                self._sanitize_document_metadata(chunked_documents)
            except Exception:
                continue
            for document in chunked_documents:
                text = normalize_whitespace(getattr(document, "page_content", ""))
                if not text:
                    continue
                chunks.append(
                    RetrievedChunk(
                        text=text,
                        metadata=dict(getattr(document, "metadata", {}) or {}),
                        score=0.0,
                    )
                )
        return sorted(
            chunks,
            key=lambda chunk: (
                str(chunk.metadata.get("document_id", "")),
                int(chunk.metadata.get("page", 0) or 0),
                str(chunk.metadata.get("chunk_id", "")),
            ),
        )

    def _prepare_pages(
        self,
        pages: list[Any],
        *,
        document_id: str,
        filename: str,
        document_hash: str,
    ) -> list[Any]:
        prepared = []
        for index, page in enumerate(pages):
            text = normalize_whitespace(getattr(page, "page_content", ""))
            if not text:
                continue
            metadata = dict(getattr(page, "metadata", {}) or {})
            metadata["document_id"] = document_id
            metadata["filename"] = filename
            metadata["document_hash"] = document_hash
            metadata["page"] = metadata.get("page", index)
            metadata["section"] = self._infer_section(text)
            prepared.append(self._copy_langchain_document(page, text=text, metadata=metadata))
        return prepared

    def _chunk_pages(self, prepared_pages: list[Any]) -> list[Any]:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunked_documents = splitter.split_documents(prepared_pages)
        for index, document in enumerate(chunked_documents):
            metadata = dict(document.metadata)
            metadata["chunk_id"] = f"{metadata['document_id']}_chunk_{index + 1}"
            metadata.setdefault("section", self._infer_section(document.page_content))
            document.metadata = metadata
        return chunked_documents

    @staticmethod
    def _sanitize_document_metadata(documents: list[Any]) -> None:
        for document in documents:
            sanitized = {}
            for key, value in dict(getattr(document, "metadata", {}) or {}).items():
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    sanitized[key] = value
                else:
                    sanitized[key] = str(value)
            document.metadata = sanitized

    @staticmethod
    def _copy_langchain_document(page: Any, *, text: str, metadata: dict) -> Any:
        from langchain_core.documents import Document

        return Document(page_content=text, metadata=metadata)

    @staticmethod
    def _infer_section(text: str) -> str | None:
        for raw_line in text.splitlines():
            line = normalize_whitespace(raw_line)
            if not line:
                continue
            if len(line) <= 90 and (line.istitle() or line.isupper() or line.endswith(":")):
                return line.rstrip(":")
            return None
        return None
