from __future__ import annotations

import re

from app.services.safety_service import SafetyService


class PostSafetyService:
    def __init__(self, safety_service: SafetyService) -> None:
        self.safety_service = safety_service
        self.unsafe_answer_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                r"\byou (have|likely have|probably have|definitely have)\b",
                r"\bthis (means|confirms|rules out)\b.*\b(diagnosis|diabetes|cancer|infection|disease)\b",
                r"\bthis is\s+(a|an)?\s*(diagnosis|diabetes|cancer|infection|disease)\b",
                r"\btake \d+(\.\d+)?\s*(mg|mcg|g|ml|tablets?|pills?|capsules?)\b",
                r"\b(increase|decrease|stop|start|double|skip) (your )?(dose|medication|insulin|antibiotic)\b",
                r"\byou do not need (urgent care|the er|emergency care)\b",
                r"\bit is safe to ignore\b",
            )
        ]

    def check(self, answer: str) -> tuple[bool, list[str]]:
        checked_answer = self._strip_safety_boilerplate(answer or "")
        findings = [pattern.pattern for pattern in self.unsafe_answer_patterns if pattern.search(checked_answer)]
        return not findings, findings

    def safe_replacement(self, category: str = "unsafe_personalized_treatment") -> str:
        return self.safety_service.refusal_message(category)

    @staticmethod
    def _strip_safety_boilerplate(answer: str) -> str:
        return re.sub(
            r"\b(?:not|no|cannot|can't|do not|don't|does not|without|avoid|must not|should not)\b"
            r"[^.\n;]{0,140}\b(diagnosis|diagnose|personalized treatment|medical advice|dosage|dose|triage)\b"
            r"[^.\n;]*",
            " ",
            answer,
            flags=re.IGNORECASE,
        )
