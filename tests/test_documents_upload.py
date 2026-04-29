from __future__ import annotations

from types import SimpleNamespace


def _patch_successful_upload(app, monkeypatch):
    document_service = app.state.services.document_service

    monkeypatch.setattr(
        document_service.pdf_loader,
        "load_pages",
        lambda _path: [
            SimpleNamespace(
                page_content="Hypertension is a chronic elevation in arterial blood pressure.",
                metadata={"page": 0},
            )
        ],
    )
    monkeypatch.setattr(
        document_service,
        "_chunk_pages",
        lambda pages: [
            SimpleNamespace(
                page_content=pages[0].page_content,
                metadata={
                    **pages[0].metadata,
                    "document_id": pages[0].metadata["document_id"],
                    "filename": pages[0].metadata["filename"],
                    "page": 0,
                    "chunk_id": "chunk_1",
                },
            )
        ],
    )
    monkeypatch.setattr(document_service.vectorstore_client, "add_documents", lambda docs: None)


def test_upload_document_success(client, app, monkeypatch):
    _patch_successful_upload(app, monkeypatch)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.pdf", b"%PDF-1.4\nmock", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "indexed"
    assert payload["filename"] == "notes.pdf"
    assert payload["page_count"] == 1
    assert payload["chunk_count"] == 1


def test_upload_rejects_invalid_extension(client):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"%PDF-1.4\nmock", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "file_validation_error"


def test_upload_rejects_corrupted_pdf(client, app, monkeypatch):
    document_service = app.state.services.document_service
    monkeypatch.setattr(document_service.pdf_loader, "load_pages", lambda _path: (_ for _ in ()).throw(Exception("bad pdf")))

    response = client.post(
        "/api/documents/upload",
        files={"file": ("broken.pdf", b"%PDF-1.4\nmock", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_pdf"


def test_upload_rejects_empty_text_pdf(client, app, monkeypatch):
    document_service = app.state.services.document_service
    monkeypatch.setattr(
        document_service.pdf_loader,
        "load_pages",
        lambda _path: [SimpleNamespace(page_content="   ", metadata={"page": 0})],
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"%PDF-1.4\nmock", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "empty_pdf"
