from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.core.config import Settings


class GeneralEducationService:
    def __init__(self, *, settings: Settings, groq_client: GroqClient) -> None:
        self.settings = settings
        self.groq_client = groq_client

    def answer(self, question: str) -> str:
        if self.settings.app_env == "test" or not self.settings.groq_api_key:
            return self._fallback_answer(question)
        prompt = (
            f"User educational request:\n{question}\n\n"
            "Answer as general medical education for a learner. "
            "Do not claim to use uploaded documents or literature sources."
        )
        return self.groq_client.generate_text(
            "general_education.txt",
            prompt,
            model_name=self.settings.groq_model_answer,
        )

    @staticmethod
    def _fallback_answer(question: str) -> str:
        return (
            f"General educational overview for: {question}\n\n"
            "MARA can explain this topic at a learning level, but this response is not based on uploaded "
            "documents or a literature search. It does not diagnose, dose, triage, or recommend personalized "
            "treatment. For a grounded answer, use uploaded-document RAG or Open Literature."
        )
