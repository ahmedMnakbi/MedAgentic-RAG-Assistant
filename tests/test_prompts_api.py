from __future__ import annotations


def test_prompt_search_returns_results(client):
    response = client.get("/api/prompts/search", params={"query": "quiz", "limit": 5})

    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert any(item["id"] == "medical-quiz-builder" for item in payload)


def test_prompt_detail_returns_template_and_variables(client):
    response = client.get("/api/prompts/medical-summary-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "medical-summary-brief"
    assert "${topic}" in payload["template"]
    assert any(item["name"] == "topic" for item in payload["variables"])


def test_prompt_improve_returns_structured_result(client):
    response = client.post(
        "/api/prompts/improve",
        json={
            "prompt": "summarize a medical topic for students",
            "outputType": "text",
            "outputFormat": "structured_json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Return:" in payload["improved_prompt"]
    assert "Use the following request without changing its meaning." not in payload["improved_prompt"]
    assert "medical education and document understanding only" not in payload["improved_prompt"]
    assert len(payload["changes"]) >= 1


def test_prompt_suggest_returns_variants(client):
    response = client.post(
        "/api/prompts/suggest",
        json={
            "task": "how to overcome anxiety",
            "audience": "teens",
            "modeHint": "pubmed",
            "outputType": "text",
            "outputFormat": "text",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_category"] == "literature-search"
    assert len(payload["suggestions"]) == 3
    assert any("PubMed-ready" in item["prompt"] for item in payload["suggestions"])
    assert payload["recommended_recipe_id"] == "pubmed-query-builder"


def test_prompt_enhance_mode_uses_improvement_response(client):
    response = client.post(
        "/api/chat/ask",
        json={
            "question": "make this prompt better for a document summary",
            "mode": "prompt_enhance",
            "enhance_prompt": False,
            "top_k": 4,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "prompt_enhance"
    assert payload["enhanced_prompt"]
    assert "medical education and document understanding only" not in payload["enhanced_prompt"]


def test_prompt_improve_does_not_invent_medical_exclusions(client):
    response = client.post(
        "/api/prompts/improve",
        json={
            "prompt": "Provide a list of relevant PubMed studies on Addison's disease.",
            "outputType": "text",
            "outputFormat": "text",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    lowered = payload["improved_prompt"].lower()
    assert "excluding studies on diagnosis" not in lowered
    assert "treatment, dosage, and triage" not in lowered


def test_prompt_improve_pubmed_recipe_becomes_actionable(client):
    response = client.post(
        "/api/prompts/improve",
        json={
            "prompt": (
                "Transform this idea into a focused PubMed search request.\n"
                "Research question: ${how to overcome anxiety}\n"
                "Population/topic: ${teens}\n"
                "Goal: ${goal:find recent educational literature}"
            ),
            "outputType": "text",
            "outputFormat": "text",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "PubMed-ready search query" in payload["improved_prompt"]
    assert "Use the following request without changing its meaning." not in payload["improved_prompt"]
