from __future__ import annotations

from app.services.rag_service import RetrievedChunk


def test_rag_mode_returns_grounded_answer(client, app, monkeypatch):
    retrieved = [
        RetrievedChunk(
            text="Insulin lowers blood glucose by promoting cellular uptake.",
            metadata={"document_id": "doc_1", "filename": "endo.pdf", "page": 1, "chunk_id": "c1"},
            score=0.12,
        )
    ]
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: retrieved)
    monkeypatch.setattr(
        app.state.services.answer_service,
        "answer",
        lambda *args, **kwargs: "According to the uploaded document, insulin lowers blood glucose by promoting cellular uptake.",
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the document say about insulin?", "mode": "rag"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "rag"
    assert len(payload["sources"]) == 1


def test_rag_no_source_returns_clear_message(client, app, monkeypatch):
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the uploaded document say about myocarditis?", "mode": "rag"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
    assert "not find this answer in the uploaded documents" in payload["answer"].lower()
