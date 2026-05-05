from __future__ import annotations

from app.services.document_scope_service import DocumentScopeService


def test_medical_text_is_classified_eligible():
    result = DocumentScopeService().classify(
        "Diabetes is a metabolic disease. Patients may have symptoms, diagnosis, treatment, and clinical follow-up."
    )

    assert result.scope_category == "medical"
    assert result.eligible_for_medical_workflows is True


def test_covid_and_diabetes_text_is_eligible():
    result = DocumentScopeService().classify(
        "COVID infection and diabetes pathophysiology are common topics in public health and clinical medicine."
    )

    assert result.scope_category == "medical"
    assert result.eligible_for_medical_workflows is True


def test_automata_text_is_non_medical_and_not_eligible():
    result = DocumentScopeService().classify(
        "Theory of languages covers automata, regular expressions, context-free grammar, and Turing machine models."
    )

    assert result.scope_category == "non_medical"
    assert result.eligible_for_medical_workflows is False


def test_unknown_scope_is_allowed_with_warning_category():
    result = DocumentScopeService().classify("A short ambiguous handout with few clear topic signals.")

    assert result.scope_category == "unknown"
    assert result.eligible_for_medical_workflows is True
