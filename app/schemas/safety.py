from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SafetyCategory = Literal[
    "safe_educational",
    "unsafe_diagnosis",
    "unsafe_dosage",
    "unsafe_triage",
    "unsafe_personalized_treatment",
]


class SafetyAssessment(BaseModel):
    allowed: bool
    category: SafetyCategory
    reason: str | None = None
