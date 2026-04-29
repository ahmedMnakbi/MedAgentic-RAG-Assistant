from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.schemas.chat import QuizItem
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
        payload = self.groq_client.generate_json(
            "quiz.txt",
            (
                f"User request:\n{question}\n\n"
                f"Retrieved document context:\n{context}\n\n"
                f"Enhanced execution prompt (preserve intent):\n{enhanced_prompt or 'Not provided.'}"
            ),
        )
        if not isinstance(payload, list):
            return []
        return [QuizItem.model_validate(item) for item in payload]
