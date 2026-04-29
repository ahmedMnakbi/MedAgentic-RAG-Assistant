from __future__ import annotations

from app.clients.groq_client import GroqClient
from app.services.rag_service import RagService, RetrievedChunk


class SimplificationService:
    def __init__(self, *, groq_client: GroqClient) -> None:
        self.groq_client = groq_client

    def simplify(
        self,
        question: str,
        retrieved_chunks: list[RetrievedChunk],
        *,
        enhanced_prompt: str | None = None,
    ) -> str:
        context = RagService.build_context(retrieved_chunks)
        user_prompt = (
            f"User request:\n{question}\n\n"
            f"Retrieved document context:\n{context}\n\n"
            f"Enhanced execution prompt (preserve intent):\n{enhanced_prompt or 'Not provided.'}"
        )
        return self.groq_client.generate_text("simplify.txt", user_prompt)
