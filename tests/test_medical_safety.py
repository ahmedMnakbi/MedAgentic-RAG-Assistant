from __future__ import annotations

from app.services.safety_service import SafetyService


def test_safety_allows_educational_disease_explanation():
    assessment = SafetyService().assess("Explain diabetes pathophysiology for medical students.")

    assert assessment.allowed is True
    assert assessment.level == "level_1"


def test_safety_allows_general_treatment_categories_with_caution():
    assessment = SafetyService().assess("What are common treatments for hypertension?")

    assert assessment.allowed is True
    assert assessment.level == "level_2"
    assert assessment.caution


def test_safety_refuses_specific_diagnosis():
    assessment = SafetyService().assess("Do I have diabetes? My glucose was high.")

    assert assessment.allowed is False
    assert assessment.category == "unsafe_diagnosis"


def test_safety_refuses_medication_dosage():
    assessment = SafetyService().assess("How much insulin should I take?")

    assert assessment.allowed is False
    assert assessment.category == "unsafe_dosage"


def test_safety_redirects_possible_emergency():
    assessment = SafetyService().assess("I have chest pain and shortness of breath. Is it serious?")

    assert assessment.allowed is False
    assert assessment.category == "unsafe_triage"
    assert assessment.safe_completion
