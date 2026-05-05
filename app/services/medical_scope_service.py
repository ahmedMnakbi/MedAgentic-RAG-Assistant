from __future__ import annotations

import re

from app.utils.text import normalize_whitespace


class MedicalScopeService:
    health_terms = (
        "medical",
        "medicine",
        "health",
        "public health",
        "clinical",
        "clinician",
        "patient",
        "diagnostic",
        "diagnosis",
        "epidemiology",
        "biostatistics",
        "screening",
        "symptom",
        "disease",
        "condition",
        "cancer",
        "diabetes",
        "asthma",
        "depression",
        "anxiety",
        "eating disorder",
        "migraine",
        "anemia",
        "hypertension",
        "overdose",
        "toxicology",
        "toxicokinetics",
        "toxicodynamics",
        "toxidrome",
        "pharmacology",
        "pharmacokinetics",
        "pharmacodynamics",
        "pathophysiology",
        "physiology",
        "anatomy",
        "infection",
        "pneumonia",
        "sepsis",
        "stroke",
        "cardiovascular",
        "kidney",
        "renal",
        "liver",
        "lung",
        "mental health",
        "therapy",
        "treatment",
        "medication",
    )
    explicit_medical_framing = (
        "as used in diagnostic",
        "diagnostic testing",
        "epidemiology",
        "biostatistics",
        "public health",
        "affected medicine",
        "medical history",
        "medical rag",
        "healthcare",
        "health care",
        "for medical students",
        "medical education",
        "toxicology students",
    )
    non_medical_terms = (
        "world war",
        "automata",
        "formal language",
        "theory of languages",
        "python programming",
        "programming",
        "software",
        "probability theory",
        "business",
        "legal contract",
        "history essay",
    )
    command_terms = ("explain", "summarize", "summary", "quiz", "make", "create", "what is", "what are")

    @classmethod
    def is_allowed_medical_request(cls, text: str) -> bool:
        lowered = normalize_whitespace(text).lower()
        if any(term in lowered for term in cls.explicit_medical_framing):
            return True
        if any(term in lowered for term in cls.non_medical_terms):
            return False
        return any(term in lowered for term in cls.health_terms)

    @classmethod
    def is_clearly_non_medical_request(cls, text: str) -> bool:
        lowered = normalize_whitespace(text).lower()
        if not lowered:
            return False
        if any(term in lowered for term in cls.explicit_medical_framing):
            return False
        if any(term in lowered for term in cls.non_medical_terms):
            return True
        if any(term in lowered for term in cls.health_terms):
            return False
        if any(term in lowered for term in cls.command_terms):
            return True
        topic = re.sub(r"^(?:please\s+)?(?:explain|summarize|make|create|quiz|what is|what are)\s+", "", lowered)
        return bool(topic and len(topic.split()) <= 6)
