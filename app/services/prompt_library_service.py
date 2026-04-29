from __future__ import annotations

import re
from dataclasses import dataclass

from app.clients.groq_client import GroqClient
from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundError
from app.schemas.prompts import (
    PromptDetail,
    PromptImproveResponse,
    PromptOutputFormat,
    PromptOutputType,
    PromptSearchResult,
    PromptVariable,
)


@dataclass(frozen=True, slots=True)
class PromptLibraryEntry:
    id: str
    title: str
    description: str
    author_name: str
    prompt_type: str
    category: str
    tags: tuple[str, ...]
    template: str


VARIABLE_PATTERN = re.compile(r"\$\{([a-zA-Z_]\w*)(?::([^}]+))?\}")

PROMPT_LIBRARY: tuple[PromptLibraryEntry, ...] = (
    PromptLibraryEntry(
        id="medical-rag-grounded-answer",
        title="Grounded Medical Answer",
        description="Answer from uploaded medical sources with page-aware grounding and limit statements.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="medical-education",
        tags=("rag", "citation", "study", "grounded"),
        template=(
            "You are an educational medical assistant.\n"
            "Question: ${question}\n"
            "Audience: ${audience:medical student}\n"
            "Use only this context:\n${document_context}\n\n"
            "Return a concise answer with source-aware wording and note missing details clearly."
        ),
    ),
    PromptLibraryEntry(
        id="medical-summary-brief",
        title="Medical Summary Brief",
        description="Summarize a medical topic or source into concise study notes.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="summarization",
        tags=("summary", "key-points", "study", "notes"),
        template=(
            "Summarize the following medical content for ${audience:medical students}.\n"
            "Topic: ${topic}\n"
            "Content:\n${content}\n\n"
            "Output: ${format:bullet list with key points and caveats}."
        ),
    ),
    PromptLibraryEntry(
        id="plain-language-rewrite",
        title="Plain-Language Rewrite",
        description="Rewrite complex medical language into simpler educational wording without adding facts.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="simplification",
        tags=("plain-language", "rewrite", "student", "clarity"),
        template=(
            "Rewrite this medical content in plain language without expanding beyond the source.\n"
            "Audience: ${audience:first-year student}\n"
            "Source:\n${content}\n\n"
            "If the source is brief, keep the explanation brief."
        ),
    ),
    PromptLibraryEntry(
        id="medical-quiz-builder",
        title="Medical Quiz Builder",
        description="Create source-grounded MCQs or short recall questions for revision.",
        author_name="MedAgentic Library",
        prompt_type="STRUCTURED",
        category="assessment",
        tags=("quiz", "mcq", "revision", "assessment"),
        template=(
            "Create ${count:3} study questions from this source.\n"
            "Topic: ${topic}\n"
            "Source:\n${content}\n\n"
            "Return JSON with question, options, correct_answer, explanation, source_pages."
        ),
    ),
    PromptLibraryEntry(
        id="pubmed-query-builder",
        title="PubMed Query Builder",
        description="Turn a rough literature question into a focused PubMed search request.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="literature-search",
        tags=("pubmed", "research", "query", "ncbi"),
        template=(
            "Transform this idea into a focused PubMed search request.\n"
            "Research question: ${question}\n"
            "Population/topic: ${population_or_topic}\n"
            "Goal: ${goal:find recent educational literature}\n"
        ),
    ),
    PromptLibraryEntry(
        id="concept-compare-grid",
        title="Concept Comparison Grid",
        description="Compare two medical concepts side by side for rapid study review.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="study-tools",
        tags=("compare", "table", "study", "concepts"),
        template=(
            "Compare ${concept_a} and ${concept_b} using only the provided source material.\n"
            "Output as ${format:a short comparison table}.\n"
            "Source:\n${content}"
        ),
    ),
    PromptLibraryEntry(
        id="teaching-outline-session",
        title="Teaching Outline Session",
        description="Build a small teaching outline from a medical source for class presentation.",
        author_name="MedAgentic Library",
        prompt_type="TEXT",
        category="teaching",
        tags=("teaching", "outline", "presentation", "lesson"),
        template=(
            "Create a teaching outline about ${topic} for ${audience:medical students}.\n"
            "Length: ${length:5 minutes}\n"
            "Source:\n${content}"
        ),
    ),
)


class PromptLibraryService:
    def __init__(self, *, settings: Settings, groq_client: GroqClient) -> None:
        self.settings = settings
        self.groq_client = groq_client
        self.entries = PROMPT_LIBRARY

    def search_prompts(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
        prompt_type: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[PromptSearchResult]:
        normalized_query = (query or "").strip().lower()
        filtered = []
        for entry in self.entries:
            if prompt_type and entry.prompt_type.lower() != prompt_type.lower():
                continue
            if category and entry.category.lower() != category.lower():
                continue
            if tag and tag.lower() not in {item.lower() for item in entry.tags}:
                continue
            score = self._score_entry(entry, normalized_query)
            if normalized_query and score == 0:
                continue
            filtered.append((score, entry))

        filtered.sort(key=lambda item: (-item[0], item[1].title))
        return [self._to_search_result(entry) for _, entry in filtered[: max(1, min(limit, 50))]]

    def get_prompt(self, prompt_id: str) -> PromptDetail:
        entry = next((item for item in self.entries if item.id == prompt_id), None)
        if entry is None:
            raise ResourceNotFoundError(f"Prompt '{prompt_id}' was not found.")

        result = self._to_search_result(entry)
        variables = self._extract_variables(entry.template)
        return PromptDetail(**result.model_dump(), template=entry.template, variables=variables)

    def improve_prompt(
        self,
        *,
        prompt: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> PromptImproveResponse:
        if self.settings.app_env == "test":
            return self._fallback_improvement(prompt, output_type=output_type, output_format=output_format)

        request_prompt = (
            f"Original prompt:\n{prompt}\n\n"
            f"Requested output type: {output_type}\n"
            f"Requested output format: {output_format}\n\n"
            "Improve this prompt for clarity, structure, and robustness while preserving the user's exact intent. "
            "Do not add domain facts, exclusion criteria, safety topics, or new sub-goals that the user did not ask for. "
            "Do not narrow or broaden the topic. "
            "Do not turn the prompt into a different task. "
            "Your job is prompt engineering only: improve structure, clarity, constraints, and output instructions."
        )
        try:
            payload = self.groq_client.generate_json("prompt_improve.txt", request_prompt, temperature=0.1)
            raw_improved_prompt = str(payload.get("improved_prompt", "")).strip()
            if not raw_improved_prompt:
                return self._fallback_improvement(prompt, output_type=output_type, output_format=output_format)

            normalized_changes = [str(item).strip() for item in payload.get("changes", []) if str(item).strip()]
            return PromptImproveResponse(
                improved_prompt=raw_improved_prompt,
                changes=normalized_changes or self._default_changes(output_type=output_type, output_format=output_format),
            )
        except Exception:
            return self._fallback_improvement(prompt, output_type=output_type, output_format=output_format)

    @staticmethod
    def _score_entry(entry: PromptLibraryEntry, query: str) -> int:
        if not query:
            return 1
        haystack = " ".join(
            [
                entry.title,
                entry.description,
                entry.category,
                " ".join(entry.tags),
                entry.template,
            ]
        ).lower()
        score = 0
        for token in query.split():
            if token in haystack:
                score += 1
            if token in entry.title.lower():
                score += 2
        return score

    def _to_search_result(self, entry: PromptLibraryEntry) -> PromptSearchResult:
        return PromptSearchResult(
            id=entry.id,
            title=entry.title,
            description=entry.description,
            author_name=entry.author_name,
            prompt_type=entry.prompt_type,
            category=entry.category,
            tags=list(entry.tags),
            link=f"/api/prompts/{entry.id}",
            has_variables=bool(VARIABLE_PATTERN.search(entry.template)),
        )

    @staticmethod
    def _extract_variables(template: str) -> list[PromptVariable]:
        results = []
        seen: set[str] = set()
        for name, default_value in VARIABLE_PATTERN.findall(template):
            if name in seen:
                continue
            seen.add(name)
            results.append(
                PromptVariable(
                    name=name,
                    default_value=default_value or None,
                    required=default_value == "",
                )
            )
        return results

    @staticmethod
    def _fallback_improvement(
        prompt: str,
        *,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> PromptImproveResponse:
        cleaned_prompt = prompt.strip()
        improved_prompt = (
            "Use the following request without changing its meaning.\n"
            f"Task:\n{cleaned_prompt}\n\n"
            "Prompt engineering instructions:\n"
            "- Preserve the user's exact intent.\n"
            "- Do not add new facts, exclusions, or sub-goals.\n"
            "- Make the response structure explicit and easy to follow.\n"
            "- If the available information is insufficient, state that clearly.\n"
            f"- Target output type: {output_type}.\n"
            f"- Target output format: {output_format}."
        )
        return PromptImproveResponse(
            improved_prompt=improved_prompt,
            changes=PromptLibraryService._default_changes(output_type=output_type, output_format=output_format),
        )

    @staticmethod
    def _default_changes(*, output_type: PromptOutputType, output_format: PromptOutputFormat) -> list[str]:
        return [
            "Added an explicit intent-preservation instruction.",
            "Added clearer response-structure guidance.",
            f"Added target output type guidance ({output_type}).",
            f"Added target output format guidance ({output_format}).",
        ]
