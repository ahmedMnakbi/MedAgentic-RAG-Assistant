from __future__ import annotations

from types import SimpleNamespace

from app.services.context_packer_service import ContextPackerService
from app.services.post_safety_service import PostSafetyService
from app.services.rag_service import RetrievedChunk
from app.services.safety_service import SafetyService


def test_context_packer_deduplicates_chunks(settings):
    packer = ContextPackerService(settings)
    chunks = [
        RetrievedChunk(
            text="Diabetes pathophysiology involves impaired insulin action.",
            metadata={"filename": "endo.pdf", "page": 0, "chunk_id": "c1"},
            score=0.1,
        ),
        RetrievedChunk(
            text="Diabetes pathophysiology involves impaired insulin action.",
            metadata={"filename": "endo.pdf", "page": 0, "chunk_id": "c2"},
            score=0.2,
        ),
    ]

    packed = packer.pack(chunks)

    assert packed.text.count("Diabetes pathophysiology") == 1
    assert packed.omitted_count == 1


def test_duplicate_upload_detected_by_hash(client, app, monkeypatch):
    document_service = app.state.services.document_service
    monkeypatch.setattr(
        document_service.pdf_loader,
        "load_pages",
        lambda _path: [SimpleNamespace(page_content="Readable medical PDF text.", metadata={"page": 0})],
    )
    monkeypatch.setattr(
        document_service,
        "_chunk_pages",
        lambda pages: [
            SimpleNamespace(page_content=pages[0].page_content, metadata={**pages[0].metadata, "chunk_id": "chunk_1"})
        ],
    )
    monkeypatch.setattr(document_service.vectorstore_client, "add_documents", lambda docs: None)

    first = client.post("/api/documents/upload", files={"file": ("a.pdf", b"%PDF-1.4\nsame", "application/pdf")})
    second = client.post("/api/documents/upload", files={"file": ("a.pdf", b"%PDF-1.4\nsame", "application/pdf")})

    assert first.json()["status"] == "indexed"
    assert second.json()["status"] == "duplicate"
    assert second.json()["document_hash"] == first.json()["document_hash"]


def test_retrieval_strategy_falls_back_safely(app):
    app.state.settings.retrieval_strategy = "unknown"

    assert app.state.services.rag_service._strategy() == "similarity"


def test_post_safety_checker_catches_unsafe_advice():
    service = PostSafetyService(SafetyService())

    ok, findings = service.check("You should take 50 mg of this medication now.")

    assert ok is False
    assert findings
