from __future__ import annotations

from types import SimpleNamespace

from app.schemas.common import QuizItem
from app.services.rag_service import RetrievedChunk


def test_rag_mode_returns_grounded_answer(client, app, monkeypatch):
    retrieved = [
        RetrievedChunk(
            text="Insulin lowers blood glucose by promoting cellular uptake.",
            metadata={"document_id": "doc_1", "filename": "endo.pdf", "page": 1, "chunk_id": "c1"},
            score=0.12,
        )
    ]
    monkeypatch.setattr(app.state.services.document_service, "list_documents", lambda: [SimpleNamespace(document_id="doc_1")])
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


def test_auto_mode_general_education_without_documents_does_not_use_rag(client):
    response = client.post(
        "/api/chat/ask",
        json={"question": "Explain diabetes pathophysiology for a medical student.", "mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "general_education"
    assert payload["sources"] == []


def test_auto_mode_uploaded_pdf_reference_uses_document_rag_no_source(client, app, monkeypatch):
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the uploaded PDF say about diabetes?", "mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
    assert payload["mode_used"] == "document_rag"


def test_explicit_rag_mode_without_documents_can_return_no_source(client, app, monkeypatch):
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/ask",
        json={"question": "Explain diabetes pathophysiology for a medical student.", "mode": "rag"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
    assert payload["mode_used"] == "rag"


def test_selected_document_quiz_uses_document_context_for_generic_pdf_prompt(client, app, monkeypatch):
    selected_chunks = [
        RetrievedChunk(
            text="Diabetes pathophysiology includes insulin resistance and impaired beta cell function.",
            metadata={"document_id": "diabetes-doc", "filename": "DIABETES.pdf", "page": 0, "chunk_id": "c1"},
            score=0.0,
        )
    ]
    captured = {}

    monkeypatch.setattr(
        app.state.services.rag_service,
        "retrieve",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("semantic retrieval should not run")),
    )
    monkeypatch.setattr(
        app.state.services.rag_service,
        "retrieve_document_chunks",
        lambda *args, **kwargs: selected_chunks,
    )
    monkeypatch.setattr(
        app.state.services.document_service,
        "list_documents",
        lambda: [SimpleNamespace(document_id="diabetes-doc")],
    )

    def fake_generate_context(question, context, **kwargs):
        captured["question"] = question
        captured["context"] = context
        return [
            QuizItem(
                question="Which mechanism is linked to type 2 diabetes?",
                options=["Insulin resistance", "Low oxygen tension"],
                correct_answer="Insulin resistance",
                explanation="The selected document context mentions insulin resistance.",
            )
        ]

    monkeypatch.setattr(app.state.services.quiz_service, "generate_context", fake_generate_context)

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "Create 5 quiz questions from this PDF.",
            "mode": "quiz",
            "document_ids": ["diabetes-doc"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "quiz"
    assert payload["quiz_items"]
    assert "Diabetes pathophysiology" in captured["context"]


def test_selected_document_quiz_falls_back_to_saved_pdf_chunks(client, app, monkeypatch):
    selected_chunks = [
        RetrievedChunk(
            text="Diabetes pathophysiology includes insulin resistance.",
            metadata={"document_id": "diabetes-doc", "filename": "DIABETES.pdf", "page": 0, "chunk_id": "c1"},
            score=0.0,
        )
    ]
    monkeypatch.setattr(
        app.state.services.rag_service,
        "retrieve_document_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("chroma unavailable")),
    )
    monkeypatch.setattr(
        app.state.services.document_service,
        "load_stored_document_chunks",
        lambda *args, **kwargs: selected_chunks,
    )
    monkeypatch.setattr(
        app.state.services.quiz_service,
        "generate_context",
        lambda *args, **kwargs: [
            QuizItem(
                question="What is a diabetes mechanism?",
                options=["Insulin resistance", "Pulmonary shunt"],
                correct_answer="Insulin resistance",
                explanation="The selected PDF context mentions insulin resistance.",
            )
        ],
    )

    response = client.post(
        "/api/chat/ask",
        json={
            "question": "Create 5 quiz questions from this PDF.",
            "mode": "quiz",
            "document_ids": ["diabetes-doc"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["quiz_items"]


def test_selected_document_summarize_and_simplify_use_saved_pdf_chunks(client, app, monkeypatch):
    selected_chunks = [
        RetrievedChunk(
            text="Diabetes mellitus involves chronic hyperglycemia.",
            metadata={"document_id": "diabetes-doc", "filename": "DIABETES.pdf", "page": 0, "chunk_id": "c1"},
            score=0.0,
        )
    ]
    monkeypatch.setattr(app.state.services.rag_service, "retrieve_document_chunks", lambda *args, **kwargs: [])
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: selected_chunks)
    monkeypatch.setattr(
        app.state.services.summarization_service,
        "summarize_context",
        lambda *args, **kwargs: "Summary: diabetes involves chronic hyperglycemia.",
    )
    monkeypatch.setattr(
        app.state.services.simplification_service,
        "simplify_context",
        lambda *args, **kwargs: "Simple explanation: diabetes means blood sugar stays high.",
    )

    summarize_response = client.post(
        "/api/chat/ask",
        json={"question": "Summarize this PDF.", "mode": "summarize", "document_ids": ["diabetes-doc"]},
    )
    simplify_response = client.post(
        "/api/chat/ask",
        json={"question": "Explain this PDF simply.", "mode": "simplify", "document_ids": ["diabetes-doc"]},
    )

    assert summarize_response.status_code == 200
    assert summarize_response.json()["status"] == "ok"
    assert simplify_response.status_code == 200
    assert simplify_response.json()["status"] == "ok"


def test_auto_uploaded_pdf_question_falls_back_cleanly_when_vectorstore_fails(client, app, monkeypatch):
    fallback_chunks = [
        RetrievedChunk(
            text="Diabetes pathophysiology includes insulin resistance and beta cell dysfunction.",
            metadata={"document_id": "diabetes-doc", "filename": "DIABETES.pdf", "page": 0, "chunk_id": "c1"},
            score=0.0,
        )
    ]
    monkeypatch.setattr(app.state.services.document_service, "list_documents", lambda: [SimpleNamespace(document_id="diabetes-doc")])
    monkeypatch.setattr(
        app.state.services.rag_service,
        "retrieve",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("chroma unavailable")),
    )
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: fallback_chunks)
    monkeypatch.setattr(
        app.state.services.answer_service,
        "answer",
        lambda *args, **kwargs: "The uploaded PDF describes diabetes as involving insulin resistance and beta cell dysfunction.",
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the uploaded PDF say about diabetes?", "mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "document_rag"


def test_deleted_document_chunks_are_filtered_from_chat(client, app, monkeypatch):
    stale_chunk = RetrievedChunk(
        text="Deleted document content about diabetes.",
        metadata={"document_id": "deleted-doc", "filename": "deleted.pdf", "page": 0, "chunk_id": "c1"},
        score=1.0,
    )
    monkeypatch.setattr(app.state.services.document_service, "list_documents", lambda: [SimpleNamespace(document_id="other-doc")])
    monkeypatch.setattr(app.state.services.rag_service, "retrieve", lambda *args, **kwargs: [stale_chunk])
    monkeypatch.setattr(app.state.services.document_service, "load_stored_document_chunks", lambda *args, **kwargs: [])

    response = client.post(
        "/api/chat/ask",
        json={"question": "What does the uploaded PDF say about diabetes?", "mode": "auto"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
