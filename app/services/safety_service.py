from __future__ import annotations

import re

from app.schemas.safety import SafetyAssessment


class SafetyService:
    def __init__(self) -> None:
        self.diagnosis_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bdiagnos(e|is|ing)\b",
                r"\bdo i have\b",
                r"\bwhat disease do i have\b",
                r"\bwhat condition do i have\b",
                r"\bwhat illness do i have\b",
                r"\bwhat is wrong with me\b",
                r"\bcan you tell me what i have\b",
            )
        ]
        self.dosage_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bhow many\s*(mg|mcg|g|ml|tablets|pills|capsules)\b",
                r"\bwhat dose should i take\b",
                r"\bwhat dosage should i take\b",
                r"\bhow often should i take\b",
                r"\bcan i take \d+\s*(mg|mcg|g|ml)\b",
            )
        ]
        self.triage_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bshould i go to the (er|emergency room|hospital)\b",
                r"\bis this an emergency\b",
                r"\bdo i need urgent care\b",
                r"\bshould i call an ambulance\b",
                r"\bchest pain\b.*\bwhat should i do\b",
                r"\btrouble breathing\b.*\bwhat should i do\b",
            )
        ]
        self.personalized_treatment_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bwhat should i take for\b",
                r"\bwhat medication should i take\b",
                r"\bwhat treatment should i get\b",
                r"\bcreate a treatment plan for me\b",
                r"\bpersonalized treatment\b",
                r"\bfor my symptoms\b",
                r"\bfor my condition\b",
                r"\bfor my father\b",
                r"\bfor my mother\b",
                r"\bfor my child\b",
                r"\bfor my patient\b",
            )
        ]

    def assess(self, question: str) -> SafetyAssessment:
        if self._matches_any(question, self.triage_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_triage",
                reason="Emergency triage and urgent care guidance are out of scope.",
            )
        if self._matches_any(question, self.dosage_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_dosage",
                reason="Medication dosage advice is out of scope.",
            )
        if self._matches_any(question, self.diagnosis_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_diagnosis",
                reason="Diagnosis requests are out of scope.",
            )
        if self._matches_any(question, self.personalized_treatment_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_personalized_treatment",
                reason="Personalized treatment recommendations are out of scope.",
            )
        return SafetyAssessment(allowed=True, category="safe_educational", reason=None)

    def refusal_message(self, category: str) -> str:
        if category == "unsafe_triage":
            return (
                "I can help with medical education and document understanding, but I cannot provide "
                "emergency triage. Please contact a licensed clinician or local emergency services "
                "for urgent medical situations."
            )
        if category == "unsafe_dosage":
            return (
                "I can help explain medical information for study purposes, but I cannot provide "
                "medication dosage advice. Please consult a licensed clinician or pharmacist."
            )
        if category == "unsafe_diagnosis":
            return (
                "I am an educational assistant for medical documents and cannot diagnose medical "
                "conditions. Please consult a licensed clinician for diagnostic advice."
            )
        return (
            "I can support medical education and document understanding, but I cannot provide "
            "personalized treatment advice. Please consult a licensed clinician."
        )

    @staticmethod
    def _matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
        return any(pattern.search(text) for pattern in patterns)
