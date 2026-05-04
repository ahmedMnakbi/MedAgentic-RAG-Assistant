from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, File, Request, UploadFile

from app.core.exceptions import AppError, ExternalServiceError
from app.schemas.documents import (
    DocumentRecord,
    DocumentDeleteResponse,
    DocumentUploadResponse,
    DocumentWorkflowRequest,
    DocumentWorkflowResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


@router.get("", response_model=list[DocumentRecord])
def list_documents(request: Request) -> list[DocumentRecord]:
    services = _get_services(request)
    return services.document_service.list_documents()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    services = _get_services(request)
    content = await file.read()
    try:
        return services.document_service.process_upload(
            filename=file.filename or "uploaded.pdf",
            content_type=file.content_type,
            content=content,
        )
    except AppError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            "Document upload failed before indexing could complete. Existing indexed documents were left unchanged."
        ) from exc


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(document_id: str, request: Request) -> DocumentDeleteResponse:
    services = _get_services(request)
    try:
        return services.document_service.delete_document(document_id)
    except AppError:
        raise
    except Exception as exc:
        raise ExternalServiceError(
            "Document deletion failed before cleanup could complete. Existing documents were left unchanged."
        ) from exc


@router.post("/workflow", response_model=DocumentWorkflowResponse)
def run_document_workflow(
    payload: DocumentWorkflowRequest,
    request: Request,
) -> DocumentWorkflowResponse:
    services = _get_services(request)
    return services.document_workflow_service.run(payload)
