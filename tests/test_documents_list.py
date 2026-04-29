from __future__ import annotations

from types import SimpleNamespace


def test_list_documents_returns_uploaded_records(client, app, monkeypatch):
    document_service = app.state.services.document_service
    monkeypatch.setattr(
        document_service.pdf_loader,
        "load_pages",
        lambda _path: [
            SimpleNamespace(page_content="Renal physiology overview.", metadata={"page": 0})
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

    upload_response = client.post(
        "/api/documents/upload",
        files={"file": ("renal.pdf", b"%PDF-1.4\nmock", "application/pdf")},
    )
    assert upload_response.status_code == 200

    list_response = client.get("/api/documents")
    payload = list_response.json()

    assert list_response.status_code == 200
    assert len(payload) == 1
    assert payload[0]["filename"] == "renal.pdf"
    assert payload[0]["document_id"].startswith("doc_")
