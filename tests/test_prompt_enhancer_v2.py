from __future__ import annotations


def test_prompt_enhance_v2_routes_uploaded_pdf_request(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={
            "raw_input": "explain diabetes from this pdf like im studying",
            "strict_grounding": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] in {"rag", "simplify"}
    assert payload["rag_query"]
    assert payload["safety_plan"]
    assert "diabetes" in payload["optimized_prompt"].lower()


def test_prompt_enhance_v2_routes_full_text_to_open_literature(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={"raw_input": "find real full text articles about sepsis pathophysiology not just abstracts"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] == "open_literature"
    assert payload["open_literature_query"]
    assert any("Full-text" in warning or "Full text" in warning for warning in payload["warnings"])


def test_prompt_enhance_v2_transforms_unsafe_diagnostic_prompt(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={"raw_input": "do i have diabetes my glucose is high"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_send_to_assistant"] is True
    assert "do i have" not in payload["optimized_prompt"].lower()
    assert "clinician" in payload["optimized_prompt"].lower()


def test_prompt_enhance_v2_blocks_or_redirects_dosage_prompt(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={"raw_input": "how much insulin should I take"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "dosage" in " ".join(payload["safety_plan"]).lower() or "dose" in payload["optimized_prompt"].lower()
    assert any("unsafe" in warning.lower() for warning in payload["warnings"])


def test_old_prompt_improve_still_works(client):
    response = client.post(
        "/api/prompts/improve",
        json={"prompt": "summarize a medical topic for students"},
    )

    assert response.status_code == 200
    assert response.json()["improved_prompt"]
