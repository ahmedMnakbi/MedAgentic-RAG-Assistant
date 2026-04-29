from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.services.rag_service import RagService, RetrievedChunk


class SummarizationService:
    def __init__(self, *, groq_client: GroqClient) -> None:
        self.groq_client = groq_client

    def summarize(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
        *,
        enhanced_prompt: str | None = None,
    ) -> str:
        context = RagService.build_context(retrieved_chunks)
        return self.summarize_context(question, context, enhanced_prompt=enhanced_prompt)

    def summarize_context(
        self,
        question: str,
        context: str,
        *,
        enhanced_prompt: str | None = None,
        context_label: str = "Retrieved document context",
    ) -> str:
        user_prompt = (
            f"User request:\n{question}\n\n"
            f"{context_label}:\n{context}\n\n"
            f"Enhanced execution prompt (preserve intent):\n{enhanced_prompt or 'Not provided.'}"
        )
        return self.groq_client.generate_text("summarize.txt", user_prompt)
