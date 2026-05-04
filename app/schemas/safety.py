from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

SafetyCategory = Literal[
    "safe_educational",
    "safe_with_caution",
    "unsafe_diagnosis",
    "unsafe_dosage",
    "unsafe_triage",
    "unsafe_personalized_treatment",
]
SafetyLevel = Literal["level_1", "level_2", "level_3"]


class SafetyAssessment(BaseModel):
    allowed: bool
    category: SafetyCategory
    reason: str | None = None
    level: SafetyLevel = "level_1"
    caution: str | None = None
    safe_completion: str | None = None
