from __future__ import annotations

from pydantic import SecretStr

from app.schemas.prompt_enhancement import PromptEnhanceV2Request
from app.services.prompt_enhancer_v2_service import PromptEnhancerV2Service
from app.services.safety_service import SafetyService


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
    assert payload["inferred_mode"] == "document_rag"
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
    assert payload["full_text_required"] is True
    assert payload["output_format"] == "markdown"
    assert payload["open_literature_query"]
    assert "not just" not in payload["open_literature_query"].lower()
    assert any("Full-text" in warning or "Full text" in warning for warning in payload["warnings"])


def test_prompt_enhance_v2_open_literature_query_is_handoff_ready(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={
            "raw_input": "find diabetes pathophysiology full text not just abstracts",
            "output_format": "evidence_table",
            "full_text_required": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] == "open_literature"
    assert payload["full_text_required"] is True
    assert payload["output_format"] == "evidence_table"
    assert payload["open_literature_query"] == "diabetes mellitus pathophysiology full text review open access"


def test_prompt_enhance_v2_general_education_without_strict_grounding(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={
            "raw_input": "Explain diabetes pathophysiology for a medical student.",
            "source_scope": "auto",
            "strict_grounding": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] == "general_education"
    assert payload["open_article_instruction"] is None
    assert payload["rag_query"] is None


def test_prompt_enhance_v2_general_education_with_strict_grounding_never_open_article(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={
            "raw_input": "Explain diabetes pathophysiology for a medical student.",
            "source_scope": "auto",
            "strict_grounding": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] == "general_education"
    assert payload["open_article_instruction"] is None
    assert payload["warnings"]


def test_prompt_enhance_v2_url_routes_to_open_article(client):
    response = client.post(
        "/api/prompts/enhance-v2",
        json={"raw_input": "Summarize this article: https://example.com/article"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["inferred_mode"] == "open_article"
    assert payload["open_article_instruction"]


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


def test_prompt_enhance_v2_llm_override_cannot_force_open_article_without_url(settings):
    class BadGroq:
        def generate_json(self, *args, **kwargs):
            return {
                "inferred_mode": "open_article",
                "optimized_prompt": "Route: open_article",
                "open_article_instruction": "Import a nonexistent article URL.",
            }

    live_settings = settings.model_copy(update={"app_env": "development", "groq_api_key": SecretStr("test")})
    service = PromptEnhancerV2Service(
        settings=live_settings,
        safety_service=SafetyService(),
        groq_client=BadGroq(),
    )

    result = service.enhance(
        PromptEnhanceV2Request(
            raw_input="Explain diabetes pathophysiology for a medical student.",
            strict_grounding=False,
        )
    )

    assert result.inferred_mode == "general_education"
    assert result.open_article_instruction is None


def test_prompt_enhance_v2_llm_override_cannot_force_open_literature_for_plain_task(settings):
    class BadGroq:
        def generate_json(self, *args, **kwargs):
            return {
                "original_input": "Task: Explain diabetes pathophysiology\nRoute: open_literature",
                "inferred_mode": "open_literature",
                "optimized_prompt": "Task: Explain diabetes pathophysiology\nRoute: open_literature",
            }

    live_settings = settings.model_copy(update={"app_env": "development", "groq_api_key": SecretStr("test")})
    service = PromptEnhancerV2Service(
        settings=live_settings,
        safety_service=SafetyService(),
        groq_client=BadGroq(),
    )

    result = service.enhance(
        PromptEnhanceV2Request(
            raw_input="Explain diabetes pathophysiology for a medical student.",
            strict_grounding=True,
        )
    )

    assert result.original_input == "Explain diabetes pathophysiology for a medical student."
    assert result.inferred_mode == "general_education"
