from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.services.rag_service import RagService, RetrievedChunk


class AnswerService:
    def __init__(self, *, groq_client: GroqClient) -> None:
        self.groq_client = groq_client

    def answer(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
        *,
        enhanced_prompt: str | None = None,
    ) -> str:
        context = RagService.build_context(retrieved_chunks)
        return self.answer_context(question, context, enhanced_prompt=enhanced_prompt)

    def answer_context(
        self,
        question: str,
        context: str,
        *,
        enhanced_prompt: str | None = None,
        context_label: str = "Retrieved document context",
    ) -> str:
        user_prompt = (
            f"User question:\n{question}\n\n"
            f"{context_label}:\n{context}\n\n"
            f"Enhanced execution prompt (preserve intent):\n{enhanced_prompt or 'Not provided.'}\n\n"
            "Answer only from the retrieved document context. If the context is incomplete, say so clearly."
        )
        settings = getattr(self.groq_client, "settings", None)
        return self.groq_client.generate_text(
            "rag_answer.txt",
            user_prompt,
            model_name=getattr(settings, "groq_model_answer", None),
        )
