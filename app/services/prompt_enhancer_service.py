from __future__ import annotations


class PromptEnhancerService:
    def enhance(self, question: str, mode: str) -> str:
        objective = self._objective_for_mode(mode)
        return (
            "Preserve the user's exact intent and do not add new medical facts or change the meaning.\n"
            f"Original user request:\n{question}\n\n"
            "Execution constraints:\n"
            "- This assistant is for medical education and document understanding only.\n"
            "- Do not provide diagnosis, dosage advice, emergency triage, or personalized treatment.\n"
            "- Use only the requested source material or cited metadata.\n"
            f"- Output style: {objective}\n"
            "- State limits clearly when the source material is insufficient."
        )

    @staticmethod
    def _objective_for_mode(mode: str) -> str:
        mapping = {
            "summarize": "Produce a concise study-oriented summary with accurate key points.",
            "simplify": "Explain the material in plain language suitable for learning.",
            "quiz": "Generate study questions with clear answers and short explanations.",
            "pubmed": "Return metadata-only PubMed search results relevant to the request.",
            "prompt_enhance": "Improve structure, constraints, and output format without changing intent.",
            "rag": "Answer from uploaded documents with source-grounded educational explanations.",
        }
        return mapping.get(mode, mapping["rag"])
