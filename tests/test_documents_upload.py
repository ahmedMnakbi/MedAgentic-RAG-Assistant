from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

from reportlab.pdfgen import canvas


def _text_pdf_bytes(text: str = "Diabetes is a metabolic disease with insulin resistance.") -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 720, text)
    pdf.save()
    return buffer.getvalue()


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


def test_upload_normal_text_pdf_indexes_successfully(client, app, monkeypatch):
    captured = {}

    def fake_add_documents(documents):
        captured["documents"] = documents

    monkeypatch.setattr(app.state.services.document_service.vectorstore_client, "add_documents", fake_add_documents)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("diabetes_notes.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "indexed"
    assert payload["chunk_count"] >= 1
    assert captured["documents"]
    assert all(value is not None for doc in captured["documents"] for value in doc.metadata.values())


def test_upload_vector_failure_degrades_to_text_only_record(client, app, monkeypatch):
    before = app.state.services.document_service.list_documents()
    monkeypatch.setattr(
        app.state.services.document_service.vectorstore_client,
        "add_documents",
        lambda _documents: (_ for _ in ()).throw(RuntimeError("vector store unavailable")),
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("indexing_failure.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "indexed_text_only"
    after = app.state.services.document_service.list_documents()
    assert len(after) == len(before) + 1


def test_upload_chunking_failure_is_specific_and_preserves_registry(client, app, monkeypatch):
    before = app.state.services.document_service.list_documents()
    monkeypatch.setattr(
        app.state.services.document_service,
        "_chunk_pages",
        lambda _pages: (_ for _ in ()).throw(RuntimeError("splitter unavailable")),
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("chunking_failure.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "external_service_error"
    assert "chunking step" in payload["error"].lower()
    assert app.state.services.document_service.list_documents() == before


def test_upload_with_bom_registry_does_not_return_internal_error(client, app, monkeypatch):
    registry_path = app.state.settings.documents_registry_file
    registry_path.write_text('{"documents": []}', encoding="utf-8-sig")
    monkeypatch.setattr(app.state.services.document_service.vectorstore_client, "add_documents", lambda _documents: None)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("bom_registry.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "indexed"


def test_upload_registry_parse_failure_is_clear_not_internal(client, app):
    registry_path = app.state.settings.documents_registry_file
    registry_path.write_text("{not-json", encoding="utf-8")

    response = client.post(
        "/api/documents/upload",
        files={"file": ("registry_broken.pdf", _text_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "external_service_error"
    assert "registry" in payload["error"].lower()


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
