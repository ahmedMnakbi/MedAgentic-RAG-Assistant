from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, File, Request, UploadFile

from app.schemas.documents import DocumentRecord, DocumentUploadResponse

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
    return services.document_service.process_upload(
        filename=file.filename or "uploaded.pdf",
        content_type=file.content_type,
        content=content,
    )
