from __future__ import annotations

from app.core.config import Settings


class LangGraphRagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> bool:
        if not self.settings.enable_langgraph_rag:
            return False
        try:
            import langgraph  # noqa: F401
        except ImportError:
            return False
        return True

    def describe_graph(self) -> list[str]:
        return [
            "classify_request",
            "safety_precheck",
            "generate_retrieval_query",
            "choose_source_route",
            "retrieve_or_search",
            "grade_retrieved_context",
            "rewrite_query_if_needed",
            "generate_grounded_answer",
            "safety_postcheck",
            "grounding_check",
            "final_response",
        ]
