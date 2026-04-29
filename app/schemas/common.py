from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict[str, str] = Field(default_factory=dict)


class QuizItem(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str
    source_pages: list[int] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
