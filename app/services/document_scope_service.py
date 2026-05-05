from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.documents import DocumentScopeCategory
from app.utils.text import normalize_whitespace


@dataclass(frozen=True)
class DocumentScopeAssessment:
    scope_category: DocumentScopeCategory
    scope_confidence: float
    scope_reason: str
    eligible_for_medical_workflows: bool


class DocumentScopeService:
    MEDICAL_TERMS = {
        "anatomy",
        "cardiovascular",
        "clinical",
        "covid",
        "diabetes",
        "diagnosis",
        "disease",
        "epidemiology",
        "health",
        "hypertension",
        "hospital",
        "infection",
        "laboratory",
        "medical",
        "medicine",
        "nursing",
        "patient",
        "blood pressure",
        "pathology",
        "pathophysiology",
        "pharmacology",
        "physiology",
        "public health",
        "symptom",
        "surgery",
        "treatment",
        "trial",
    }
    MEDICAL_ADJACENT_TERMS = {
        "biology",
        "biomedical",
        "biochemistry",
        "bioethics",
        "genetics",
        "microbiology",
        "neuroscience",
        "nutrition",
        "psychology",
        "wellness",
    }
    NON_MEDICAL_TERMS = {
        "automata",
        "business report",
        "compiler",
        "context-free grammar",
        "deterministic finite",
        "formal language",
        "history essay",
        "legal contract",
        "mathematics",
        "programming manual",
        "regular expression",
        "software documentation",
        "theory of languages",
        "turing machine",
    }

    def classify(self, text: str) -> DocumentScopeAssessment:
        sample = normalize_whitespace(text)[:20000].lower()
        if not sample:
            return DocumentScopeAssessment(
                scope_category="unknown",
                scope_confidence=0.0,
                scope_reason="No readable text sample was available for scope classification.",
                eligible_for_medical_workflows=True,
            )

        medical_hits = self._hits(sample, self.MEDICAL_TERMS)
        adjacent_hits = self._hits(sample, self.MEDICAL_ADJACENT_TERMS)
        non_medical_hits = self._hits(sample, self.NON_MEDICAL_TERMS)

        if len(medical_hits) >= 2 or (medical_hits and not non_medical_hits):
            return DocumentScopeAssessment(
                scope_category="medical",
                scope_confidence=min(0.95, 0.55 + 0.08 * len(medical_hits)),
                scope_reason=f"Medical education terms detected: {', '.join(medical_hits[:5])}.",
                eligible_for_medical_workflows=True,
            )

        if adjacent_hits and not non_medical_hits:
            return DocumentScopeAssessment(
                scope_category="medical_adjacent",
                scope_confidence=min(0.8, 0.45 + 0.08 * len(adjacent_hits)),
                scope_reason=f"Medical-adjacent science terms detected: {', '.join(adjacent_hits[:5])}.",
                eligible_for_medical_workflows=True,
            )

        if non_medical_hits and not medical_hits:
            return DocumentScopeAssessment(
                scope_category="non_medical",
                scope_confidence=min(0.95, 0.6 + 0.08 * len(non_medical_hits)),
                scope_reason=f"Non-medical topic terms detected: {', '.join(non_medical_hits[:5])}.",
                eligible_for_medical_workflows=False,
            )

        return DocumentScopeAssessment(
            scope_category="unknown",
            scope_confidence=0.25,
            scope_reason="The document did not contain enough clear medical or non-medical scope signals.",
            eligible_for_medical_workflows=True,
        )

    @staticmethod
    def _hits(sample: str, terms: set[str]) -> list[str]:
        hits = []
        for term in sorted(terms):
            pattern = r"\b" + re.escape(term).replace(r"\ ", r"\s+") + r"\b"
            if re.search(pattern, sample):
                hits.append(term)
        return hits
