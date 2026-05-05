from __future__ import annotations

from app.schemas.common import QuizItem
from app.schemas.documents import DocumentRecord
from app.services.rag_service import RetrievedChunk


def _record(
    document_id: str,
    *,
    filename: str = "doc.pdf",
    scope_category: str = "medical",
    eligible: bool = True,
) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        filename=filename,
        page_count=1,
        chunk_count=1,
        uploaded_at="2026-01-01T00:00:00+00:00",
        indexing_status="indexed",
        scope_category=scope_category,
        scope_confidence=0.9,
        scope_reason="test scope",
        eligible_for_medical_workflows=eligible,
    )


def _chunk(document_id: str, filename: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        metadata={"document_id": document_id, "filename": filename, "page": 0, "chunk_id": f"{document_id}_chunk_1"},
        score=0.0,
    )


def test_non_medical_selected_document_summarize_returns_scope_refusal(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("automata-doc", filename="automata.pdf", scope_category="non_medical", eligible=False)],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize this PDF.", "mode": "summarize", "document_ids": ["automata-doc"]},
    )

    payload = response.json()
    assert payload["status"] == "refused"
    assert "outside MARA's medical education scope" in payload["answer"]


def test_non_medical_selected_document_quiz_returns_scope_refusal(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("automata-doc", filename="automata.pdf", scope_category="non_medical", eligible=False)],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Create 5 quiz questions from this PDF.", "mode": "quiz", "document_ids": ["automata-doc"]},
    )

    payload = response.json()
    assert payload["status"] == "refused"
    assert "outside MARA's medical education scope" in payload["answer"]


def test_unknown_scope_document_is_used_with_warning(client, app, monkeypatch):
    chunks = [_chunk("unknown-doc", "unknown.pdf", "Diabetes is mentioned briefly in this ambiguous document.")]
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("unknown-doc", filename="unknown.pdf", scope_category="unknown", eligible=True)],
    )
    monkeypatch.setattr(app.state.services.rag_service, "retrieve_document_chunks", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(app.state.services.summarization_service, "summarize_context", lambda *args, **kwargs: "Summary.")

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize this PDF.", "mode": "summarize", "document_ids": ["unknown-doc"]},
    )

    payload = response.json()
    assert payload["status"] == "ok"
    assert any("unknown scope" in warning.lower() for warning in payload["warnings"])


def test_search_all_summarize_generic_prompt_uses_eligible_documents(client, app, monkeypatch):
    chunks = [_chunk("medical-doc", "diabetes.pdf", "Diabetes mellitus involves chronic hyperglycemia.")]
    captured = {}
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("medical-doc", filename="diabetes.pdf")],
    )
    monkeypatch.setattr(app.state.services.rag_service, "retrieve_document_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: chunks)

    def summarize_context(question, context, **kwargs):
        captured["context"] = context
        return "Summary: diabetes mellitus involves chronic hyperglycemia."

    monkeypatch.setattr(app.state.services.summarization_service, "summarize_context", summarize_context)

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize the uploaded PDF document.", "mode": "summarize", "document_ids": None},
    )

    payload = response.json()
    assert payload["status"] == "ok"
    assert "chronic hyperglycemia" in captured["context"]


def test_search_all_quiz_generic_prompt_uses_eligible_documents(client, app, monkeypatch):
    chunks = [_chunk("medical-doc", "diabetes.pdf", "Diabetes pathophysiology includes insulin resistance.")]
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("medical-doc", filename="diabetes.pdf")],
    )
    monkeypatch.setattr(app.state.services.rag_service, "retrieve_document_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(
        app.state.services.quiz_service,
        "generate_context",
        lambda *args, **kwargs: [
            QuizItem(
                question="What mechanism is mentioned?",
                options=["Insulin resistance"],
                correct_answer="Insulin resistance",
                explanation="The uploaded document mentions insulin resistance.",
            )
        ],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Create 5 quiz questions from the uploaded documents.", "mode": "quiz", "document_ids": None},
    )

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["quiz_items"]


def test_search_all_excludes_non_medical_documents(client, app, monkeypatch):
    chunks = [
        _chunk("medical-doc", "diabetes.pdf", "Diabetes pathophysiology includes insulin resistance."),
        _chunk("automata-doc", "automata.pdf", "Theory of languages includes automata and formal grammar."),
    ]
    captured = {}
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [
            _record("medical-doc", filename="diabetes.pdf"),
            _record("automata-doc", filename="automata.pdf", scope_category="non_medical", eligible=False),
        ],
    )
    monkeypatch.setattr(app.state.services.rag_service, "retrieve_document_chunks", lambda *args, **kwargs: chunks)

    def summarize_context(question, context, **kwargs):
        captured["context"] = context
        return "Summary."

    monkeypatch.setattr(app.state.services.summarization_service, "summarize_context", summarize_context)

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize the uploaded PDF document.", "mode": "summarize"},
    )

    payload = response.json()
    assert payload["status"] == "ok"
    assert "insulin resistance" in captured["context"]
    assert "formal grammar" not in captured["context"]
    assert any("Skipped 1 out-of-scope document" in warning for warning in payload["warnings"])


def test_search_all_returns_clear_message_when_no_eligible_documents(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("automata-doc", filename="automata.pdf", scope_category="non_medical", eligible=False)],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize the uploaded PDF document.", "mode": "summarize"},
    )

    payload = response.json()
    assert payload["status"] == "no_source"
    assert "No eligible medical documents" in payload["answer"]


def test_search_all_direct_text_fallback_when_vector_retrieval_fails(client, app, monkeypatch):
    chunks = [_chunk("medical-doc", "diabetes.pdf", "Diabetes involves insulin resistance.")]
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("medical-doc", filename="diabetes.pdf")],
    )
    monkeypatch.setattr(
        app.state.services.rag_service,
        "retrieve_document_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("vector unavailable")),
    )
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(app.state.services.summarization_service, "summarize_context", lambda *args, **kwargs: "Summary.")

    response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize the uploaded PDF document.", "mode": "summarize"},
    )

    assert response.json()["status"] == "ok"


def test_deleted_or_stale_docs_are_not_retrieved_in_search_all(client, app, monkeypatch):
    stale_chunk = _chunk("deleted-doc", "deleted.pdf", "Deleted diabetes content.")
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [_record("medical-doc", filename="diabetes.pdf")],
    )
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: [stale_chunk])
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the uploaded PDF say about diabetes?", "mode": "auto"},
    )

    assert response.json()["status"] == "no_source"
