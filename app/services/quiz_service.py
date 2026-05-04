from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.schemas.common import QuizItem
from app.services.rag_service import RagService, RetrievedChunk


class QuizService:
    def __init__(self, *, groq_client: GroqClient) -> None:
        self.groq_client = groq_client

    def generate(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
        *,
        enhanced_prompt: str | None = None,
    ) -> list[QuizItem]:
        context = RagService.build_context(retrieved_chunks)
        return self.generate_context(question, context, enhanced_prompt=enhanced_prompt)

    def generate_context(
        self,
        question: str,
        context: str,
        *,
        enhanced_prompt: str | None = None,
        context_label: str = "Retrieved document context",
    ) -> list[QuizItem]:
        settings = getattr(self.groq_client, "settings", None)
        payload = self.groq_client.generate_json(
            "quiz.txt",
            (
                f"User request:\n{question}\n\n"
                f"{context_label}:\n{context}\n\n"
                f"Enhanced execution prompt (preserve intent):\n{enhanced_prompt or 'Not provided.'}"
            ),
            model_name=getattr(settings, "groq_model_answer", None),
        )
        if not isinstance(payload, list):
            return []
        quiz_items: list[QuizItem] = []
        for item in payload:
            quiz_item = QuizItem.model_validate(item)
            normalized_options: list[str] = []
            for option in quiz_item.options:
                cleaned_option = option.strip()
                if cleaned_option and cleaned_option not in normalized_options:
                    normalized_options.append(cleaned_option)
            if quiz_item.correct_answer and quiz_item.correct_answer not in normalized_options:
                normalized_options.append(quiz_item.correct_answer)
            quiz_item.options = normalized_options
            quiz_items.append(quiz_item)
        return quiz_items
