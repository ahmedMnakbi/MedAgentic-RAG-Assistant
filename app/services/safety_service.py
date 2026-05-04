from __future__ import annotations

import re

from app.schemas.safety import SafetyAssessment


class SafetyService:
    def __init__(self) -> None:
        self.diagnosis_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bdo i have\b",
                r"\bwhat disease do i have\b",
                r"\bwhat condition do i have\b",
                r"\bwhat illness do i have\b",
                r"\bwhat is wrong with me\b",
                r"\bcan you tell me what i have\b",
                r"\bcan you diagnose\b",
                r"\bdiagnose my\b",
                r"\bdiagnosis for my\b",
                r"\bdo these symptoms mean\b",
            )
        ]
        self.dosage_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bhow many\s*(mg|mcg|g|ml|tablets|pills|capsules)\b",
                r"\bhow much\b.*\bshould i take\b",
                r"\bwhat dose should i take\b",
                r"\bwhat dosage should i take\b",
                r"\bwhat dosage\b.*\bfor\b",
                r"\bwhat dose\b.*\bfor\b",
                r"\bhow often should i take\b",
                r"\bcan i take \d+\s*(mg|mcg|g|ml)\b",
                r"\bis \d+(\.\d+)?\s*(mg|mcg|g|ml)\b.*\b(good|safe|correct|appropriate|recommended|enough|too much|too little)\b",
                r"\b(good|safe|correct|appropriate|recommended)\s+(dose|dosage)\b",
            )
        ]
        self.dosage_unit_pattern = re.compile(
            r"\b\d+(\.\d+)?\s*(mg|mcg|g|ml|tablets?|pills?|capsules?)\b",
            re.IGNORECASE,
        )
        self.dosage_term_pattern = re.compile(r"\b(dose|dosage|dosing)\b", re.IGNORECASE)
        self.dosage_advice_pattern = re.compile(
            r"\b(good|safe|correct|appropriate|recommended|enough|too much|too little|should i take)\b",
            re.IGNORECASE,
        )
        self.triage_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\bshould i go to the (er|emergency room|hospital)\b",
                r"\bis this an emergency\b",
                r"\bis (it|this) serious\b",
                r"\bis (it|this) safe to ignore\b",
                r"\bam i okay\b",
                r"\bshould i worry\b",
                r"\bdo i need urgent care\b",
                r"\bshould i call an ambulance\b",
                r"\bchest pain\b.*\bwhat should i do\b",
                r"\btrouble breathing\b.*\bwhat should i do\b",
                r"\b(chest pain|shortness of breath|trouble breathing|stroke symptoms|severe bleeding|unconscious|suicidal)\b.*\b(serious|safe|ignore|urgent|emergency|worry)\b",
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
        self.caution_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\b(common|general|usual|standard)\s+(treatments?|management|therapy|medication classes)\b",
                r"\btreatment (categories|options|approaches)\b",
                r"\bhow (doctors|clinicians) (evaluate|treat|manage|interpret)\b",
                r"\bgeneral (interpretation|overview) of (labs?|symptoms?|test results?)\b",
                r"\bdifferential diagnosis\b.*\b(concept|learning|education|general)\b",
            )
        ]

    def assess(self, question: str) -> SafetyAssessment:
        if self._matches_any(question, self.triage_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_triage",
                reason="Emergency triage and urgent care guidance are out of scope.",
                level="level_3",
                safe_completion=self.safe_completion(question, "unsafe_triage"),
            )
        if self._is_unsafe_dosage_request(question):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_dosage",
                reason="Medication dosage advice is out of scope.",
                level="level_3",
                safe_completion=self.safe_completion(question, "unsafe_dosage"),
            )
        if self._matches_any(question, self.diagnosis_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_diagnosis",
                reason="Diagnosis requests are out of scope.",
                level="level_3",
                safe_completion=self.safe_completion(question, "unsafe_diagnosis"),
            )
        if self._matches_any(question, self.personalized_treatment_patterns):
            return SafetyAssessment(
                allowed=False,
                category="unsafe_personalized_treatment",
                reason="Personalized treatment recommendations are out of scope.",
                level="level_3",
                safe_completion=self.safe_completion(question, "unsafe_personalized_treatment"),
            )
        if self._matches_any(question, self.caution_patterns):
            return SafetyAssessment(
                allowed=True,
                category="safe_with_caution",
                reason="General clinical background is allowed for education, but must not become personalized advice.",
                level="level_2",
                caution=self.caution_message(),
            )
        return SafetyAssessment(allowed=True, category="safe_educational", reason=None)

    def refusal_message(self, category: str) -> str:
        if category == "unsafe_triage":
            return (
                "I can help with medical education and document understanding, but I cannot provide "
                "emergency triage or decide whether symptoms are safe to ignore. If this may be urgent, "
                "please seek emergency medical help immediately."
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
    def caution_message() -> str:
        return (
            "This is general medical education. A qualified clinician must interpret symptoms, labs, "
            "tests, and treatment choices in the full clinical context."
        )

    def safe_completion(self, question: str, category: str) -> str:
        if category == "unsafe_diagnosis":
            return (
                "Explain generally how clinicians evaluate this topic, what information is usually considered, "
                "and why a diagnosis cannot be confirmed or ruled out without professional assessment."
            )
        if category == "unsafe_dosage":
            return (
                "Explain the medication class or concept at a high level without giving dose, dose changes, "
                "start/stop instructions, or personalized medication advice."
            )
        if category == "unsafe_triage":
            return (
                "Provide only a brief safety redirect for possible urgent symptoms and avoid reassurance, "
                "risk scoring, or triage decisions."
            )
        return (
            "Transform the request into general educational background and avoid personalized clinical decisions."
        )

    def educationalize(self, question: str, category: str) -> str:
        if category == "unsafe_diagnosis":
            return (
                "Explain generally how clinicians evaluate possible diabetes or other conditions related to the "
                "user's concern, what tests are commonly used, and why a clinician must interpret results in context."
                if "glucose" in question.lower() or "diabetes" in question.lower()
                else "Explain the relevant medical concept generally for education without diagnosing a specific person."
            )
        if category == "unsafe_dosage":
            return "Explain the medication or treatment concept generally for education without dosage guidance."
        if category == "unsafe_triage":
            return "Explain why urgent symptoms require professional emergency assessment without triaging the user."
        return "Explain the topic as general medical education without personalized treatment recommendations."

    @staticmethod
    def _matches_any(text: str, patterns: list[re.Pattern[str]]) -> bool:
        return any(pattern.search(text) for pattern in patterns)

    def _is_unsafe_dosage_request(self, question: str) -> bool:
        if self._matches_any(question, self.dosage_patterns):
            return True

        has_unit = bool(self.dosage_unit_pattern.search(question))
        has_dosage_term = bool(self.dosage_term_pattern.search(question))
        has_advice_term = bool(self.dosage_advice_pattern.search(question))
        return has_unit and (has_dosage_term or has_advice_term)
