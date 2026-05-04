from __future__ import annotations

from app.schemas.pubmed import PubMedArticle
from app.services.rag_service import RetrievedChunk


def test_auto_router_uses_summarize_mode(client, app, monkeypatch):
    retrieved = [
        RetrievedChunk(
            text="The nephron includes the glomerulus and renal tubule.",
            metadata={"document_id": "doc_1", "filename": "renal.pdf", "page": 0, "chunk_id": "c1"},
            score=0.08,
        )
    ]
    monkeypatch.setattr(app.state.services.document_service, "list_documents", lambda: [object()])
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: retrieved)
    monkeypatch.setattr(
        app.state.services.summarization_service,
        "summarize",
        lambda *args, **kwargs: "Summary: the nephron contains the glomerulus and renal tubule.",
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize the uploaded document's key points about nephron structure.", "mode": "auto"},
    )

    assert response.status_code == 200
    assert response.json()["mode_used"] == "summarize"


def test_auto_router_uses_pubmed_mode(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "search",
        lambda *args, **kwargs: [
            PubMedArticle(
                pmid="12345",
                title="Sample article",
                authors=["A. Author"],
                journal="Medical Journal",
                publication_date="2024",
                pubmed_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
            )
        ],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Find PubMed studies about sepsis biomarkers.", "mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode_used"] == "pubmed"
    assert len(payload["pubmed_results"]) == 1
