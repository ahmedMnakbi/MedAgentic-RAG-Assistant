from __future__ import annotations

import re
from dataclasses import dataclass

from app.clients.groq_client import GroqClient
from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundError
from app.schemas.prompts import (
    PromptDetail,
    PromptImproveResponse,
    PromptModeHint,
    PromptOutputFormat,
    PromptOutputType,
    PromptSearchResult,
    PromptSuggestion,
    PromptSuggestResponse,
    PromptVariable,
)
from app.utils.text import normalize_whitespace


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
MODE_CATEGORY_MAP = {
    "rag": "medical-education",
    "summarize": "summarization",
    "simplify": "simplification",
    "quiz": "assessment",
    "pubmed": "literature-search",
    "prompt_enhance": "study-tools",
}

PROMPT_LIBRARY: tuple[PromptLibraryEntry, ...] = (
    PromptLibraryEntry(
        id="medical-rag-grounded-answer",
        title="Grounded Medical Answer",
        description="Answer from uploaded medical sources with page-aware grounding and limit statements.",
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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
        author_name="MARA Prompt Studio",
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

    def suggest_prompts(
        self,
        *,
        task: str,
        audience: str | None,
        mode_hint: PromptModeHint,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> PromptSuggestResponse:
        inferred_category, resolved_mode = self._infer_prompt_category(task, mode_hint)
        recommended_recipe_id = self._recommended_recipe_id(task, inferred_category)
        return self._fallback_suggestions(
            task=task,
            audience=audience,
            inferred_category=inferred_category,
            mode_hint_used=resolved_mode,
            output_type=output_type,
            output_format=output_format,
            recommended_recipe_id=recommended_recipe_id,
        )

    def improve_prompt(
        self,
        *,
        prompt: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> PromptImproveResponse:
        inferred_category, _ = self._infer_prompt_category(prompt, "auto")
        heuristic = self._fallback_improvement(
            prompt,
            output_type=output_type,
            output_format=output_format,
            inferred_category=inferred_category,
        )
        if self._prefer_structured_rewrite(prompt, inferred_category=inferred_category):
            return heuristic

        if self.settings.app_env == "test":
            return heuristic

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
                return heuristic

            normalized_changes = [str(item).strip() for item in payload.get("changes", []) if str(item).strip()]
            if self._is_weak_improvement(raw_improved_prompt, original_prompt=prompt):
                return heuristic
            return PromptImproveResponse(
                improved_prompt=raw_improved_prompt,
                changes=normalized_changes or self._default_changes(output_type=output_type, output_format=output_format),
            )
        except Exception:
            return heuristic

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
        inferred_category: str,
    ) -> PromptImproveResponse:
        cleaned_prompt = prompt.strip()
        improved_prompt = PromptLibraryService._build_actionable_improvement(
            cleaned_prompt,
            inferred_category=inferred_category,
            output_type=output_type,
            output_format=output_format,
        )
        return PromptImproveResponse(
            improved_prompt=improved_prompt,
            changes=PromptLibraryService._category_changes(
                inferred_category,
                output_type=output_type,
                output_format=output_format,
            ),
        )

    @staticmethod
    def _default_changes(*, output_type: PromptOutputType, output_format: PromptOutputFormat) -> list[str]:
        return [
            "Added an explicit intent-preservation instruction.",
            "Added clearer response-structure guidance.",
            f"Added target output type guidance ({output_type}).",
            f"Added target output format guidance ({output_format}).",
        ]

    def _build_suggestion_request(
        self,
        *,
        task: str,
        audience: str | None,
        inferred_category: str,
        mode_hint: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> str:
        recipe_examples = self.search_prompts(query=task, limit=3, category=inferred_category)
        recipe_context = "\n".join(
            f"- {item.title}: {item.description}" for item in recipe_examples
        ) or "- No closely matching local prompt recipes were found."
        return (
            f"Task idea:\n{task}\n\n"
            f"Audience hint: {audience or 'Not provided'}\n"
            f"Mode hint: {mode_hint}\n"
            f"Inferred category: {inferred_category}\n"
            f"Requested output type: {output_type}\n"
            f"Requested output format: {output_format}\n\n"
            f"Relevant local prompt recipes:\n{recipe_context}"
        )

    def _parse_suggestions_payload(
        self,
        payload: object,
        *,
        inferred_category: str,
    ) -> list[PromptSuggestion]:
        if not isinstance(payload, dict):
            return []
        raw_items = payload.get("suggestions", [])
        if not isinstance(raw_items, list):
            return []
        suggestions: list[PromptSuggestion] = []
        for index, item in enumerate(raw_items[:3], start=1):
            if not isinstance(item, dict):
                continue
            prompt_text = normalize_whitespace(str(item.get("prompt", "")).replace("\\n", "\n"))
            if not prompt_text:
                continue
            suggestions.append(
                PromptSuggestion(
                    id=f"suggestion-{index}",
                    title=normalize_whitespace(str(item.get("title", "") or f"Prompt Variant {index}")),
                    prompt=prompt_text,
                    rationale=normalize_whitespace(str(item.get("rationale", "") or "Alternative phrasing for the same task.")),
                    category=inferred_category,
                    tags=[normalize_whitespace(str(tag)) for tag in item.get("tags", []) if normalize_whitespace(str(tag))],
                )
            )
        return suggestions

    def _fallback_suggestions(
        self,
        *,
        task: str,
        audience: str | None,
        inferred_category: str,
        mode_hint_used: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
        recommended_recipe_id: str | None,
    ) -> PromptSuggestResponse:
        suggestions = self._build_fallback_suggestions(
            task=task,
            audience=audience,
            inferred_category=inferred_category,
            output_type=output_type,
            output_format=output_format,
        )
        return PromptSuggestResponse(
            inferred_category=inferred_category,
            mode_hint_used=mode_hint_used,
            recommended_recipe_id=recommended_recipe_id,
            suggestions=suggestions,
        )

    def _recommended_recipe_id(self, task: str, inferred_category: str) -> str | None:
        matches = self.search_prompts(query=task, category=inferred_category, limit=1)
        return matches[0].id if matches else None

    @staticmethod
    def _infer_prompt_category(task: str, mode_hint: PromptModeHint) -> tuple[str, str]:
        resolved_mode = mode_hint
        lowered = task.lower()
        if resolved_mode == "auto":
            if any(keyword in lowered for keyword in ("pubmed", "ncbi", "study", "studies", "paper", "literature")):
                resolved_mode = "pubmed"
            elif any(keyword in lowered for keyword in ("quiz", "mcq", "question bank", "flashcard", "test me")):
                resolved_mode = "quiz"
            elif any(keyword in lowered for keyword in ("simplify", "plain language", "easy terms", "explain simply")):
                resolved_mode = "simplify"
            elif any(keyword in lowered for keyword in ("summarize", "summary", "key points", "overview")):
                resolved_mode = "summarize"
            elif "prompt" in lowered and any(keyword in lowered for keyword in ("improve", "rewrite", "enhance")):
                resolved_mode = "prompt_enhance"
            else:
                resolved_mode = "rag"
        return MODE_CATEGORY_MAP.get(resolved_mode, "medical-education"), resolved_mode

    @staticmethod
    def _is_weak_improvement(improved_prompt: str, *, original_prompt: str) -> bool:
        lowered = improved_prompt.lower()
        if improved_prompt.strip() == original_prompt.strip():
            return True
        return (
            "use the following request without changing its meaning" in lowered
            or "prompt engineering instructions:" in lowered
        )

    @staticmethod
    def _prefer_structured_rewrite(prompt: str, *, inferred_category: str) -> bool:
        lowered = prompt.lower()
        return (
            "${" in prompt
            or "research question:" in lowered
            or "population/topic:" in lowered
            or "goal:" in lowered
            or inferred_category == "literature-search"
        )

    @staticmethod
    def _build_fallback_suggestions(
        *,
        task: str,
        audience: str | None,
        inferred_category: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> list[PromptSuggestion]:
        cleaned_task = normalize_whitespace(task)
        audience_line = audience.strip() if audience else "medical students"
        formatter_line = PromptLibraryService._format_instruction(output_type, output_format)

        if inferred_category == "literature-search":
            return [
                PromptSuggestion(
                    id="suggest-direct-search",
                    title="Direct PubMed Search Prompt",
                    prompt=(
                        "Create a focused PubMed search strategy using the following inputs:\n"
                        f"- Research question or topic: {cleaned_task}\n"
                        f"- Audience or context: {audience_line}\n\n"
                        "Return:\n"
                        "1. One concise PubMed-ready search query\n"
                        "2. Important keywords or synonyms to include\n"
                        "3. Optional filters or refinements that could improve relevance\n"
                        f"{formatter_line}"
                    ),
                    rationale="Best when you want a clean search query plus keywords and filters.",
                    category=inferred_category,
                    tags=["pubmed", "search", "focused"],
                ),
                PromptSuggestion(
                    id="suggest-structured-search",
                    title="Structured Search Planner",
                    prompt=(
                        "Turn this topic into a structured PubMed search plan.\n"
                        f"Topic or question: {cleaned_task}\n"
                        f"Population or audience focus: {audience_line}\n\n"
                        "Return:\n"
                        "1. Primary search query\n"
                        "2. Alternate search query\n"
                        "3. Key synonyms or related terms\n"
                        "4. Suggested date or study-type filters\n"
                        f"{formatter_line}"
                    ),
                    rationale="Good for class demos because it shows both a main query and a backup query.",
                    category=inferred_category,
                    tags=["pubmed", "planning", "variants"],
                ),
                PromptSuggestion(
                    id="suggest-screening-search",
                    title="Search and Screening Prompt",
                    prompt=(
                        "Create a PubMed search prompt for this question and prepare it for quick study screening.\n"
                        f"Question: {cleaned_task}\n"
                        f"Audience: {audience_line}\n\n"
                        "Return:\n"
                        "1. A PubMed-ready query\n"
                        "2. A short list of keywords to keep in mind when screening titles\n"
                        "3. A one-sentence note on what would make a study relevant\n"
                        f"{formatter_line}"
                    ),
                    rationale="Useful when you want MARA to help search and quickly judge relevance.",
                    category=inferred_category,
                    tags=["pubmed", "screening", "study-selection"],
                ),
            ]

        if inferred_category == "summarization":
            return [
                PromptSuggestion(
                    id="suggest-summary-brief",
                    title="Concise Study Summary",
                    prompt=(
                        f"Summarize this medical material for {audience_line}.\n\n"
                        "Return:\n"
                        "1. A short overview\n"
                        "2. Key points\n"
                        "3. Important caveats or missing details\n"
                        f"{formatter_line}"
                    ),
                    rationale="Best for quick revision notes with clear structure.",
                    category=inferred_category,
                    tags=["summary", "study-notes", "concise"],
                ),
                PromptSuggestion(
                    id="suggest-summary-exam",
                    title="Exam-Focused Summary",
                    prompt=(
                        f"Summarize this medical topic for {audience_line} with an exam-focused structure.\n\n"
                        "Return:\n"
                        "1. Core concept\n"
                        "2. High-yield facts\n"
                        "3. Common misunderstandings or pitfalls\n"
                        f"{formatter_line}"
                    ),
                    rationale="Better when the output needs to feel high-yield and test-oriented.",
                    category=inferred_category,
                    tags=["summary", "exam", "high-yield"],
                ),
                PromptSuggestion(
                    id="suggest-summary-teaching",
                    title="Teach-Back Summary",
                    prompt=(
                        f"Summarize this medical material so that {audience_line} can explain it back clearly.\n\n"
                        "Return:\n"
                        "1. Main idea\n"
                        "2. Supporting points\n"
                        "3. A short closing recap\n"
                        f"{formatter_line}"
                    ),
                    rationale="Good for classroom presentations and short oral explanations.",
                    category=inferred_category,
                    tags=["summary", "teaching", "recap"],
                ),
            ]

        if inferred_category == "simplification":
            return [
                PromptSuggestion(
                    id="suggest-simplify-plain",
                    title="Plain-Language Rewrite",
                    prompt=(
                        f"Rewrite this medical content in plain language for {audience_line}.\n\n"
                        "Return:\n"
                        "1. A simple explanation\n"
                        "2. Short definitions for difficult terms only if they appear in the source\n"
                        "3. A brief recap sentence\n"
                        f"{formatter_line}"
                    ),
                    rationale="Best when the goal is clarity without adding new facts.",
                    category=inferred_category,
                    tags=["simplify", "plain-language", "clarity"],
                ),
                PromptSuggestion(
                    id="suggest-simplify-stepwise",
                    title="Stepwise Explanation Prompt",
                    prompt=(
                        f"Explain this medical content step by step for {audience_line}.\n\n"
                        "Return:\n"
                        "1. What it means\n"
                        "2. Why it matters in this context\n"
                        "3. A short simple recap\n"
                        f"{formatter_line}"
                    ),
                    rationale="Helpful when the material is dense and needs guided unpacking.",
                    category=inferred_category,
                    tags=["simplify", "step-by-step", "teaching"],
                ),
                PromptSuggestion(
                    id="suggest-simplify-glossary",
                    title="Simplify with Mini Glossary",
                    prompt=(
                        f"Simplify this medical content for {audience_line} without adding outside facts.\n\n"
                        "Return:\n"
                        "1. A short plain-language explanation\n"
                        "2. A mini glossary for only the hardest terms already present\n"
                        f"{formatter_line}"
                    ),
                    rationale="Good when you want simpler wording plus just enough terminology support.",
                    category=inferred_category,
                    tags=["simplify", "glossary", "student"],
                ),
            ]

        if inferred_category == "assessment":
            return [
                PromptSuggestion(
                    id="suggest-quiz-mcq",
                    title="MCQ Quiz Builder",
                    prompt=(
                        "Create source-grounded multiple-choice questions from this medical content.\n\n"
                        "Return JSON with:\n"
                        "- question\n"
                        "- options\n"
                        "- correct_answer\n"
                        "- explanation\n"
                        "- source_pages or source_titles if available"
                    ),
                    rationale="Best for structured revision quizzes and API-friendly outputs.",
                    category=inferred_category,
                    tags=["quiz", "mcq", "json"],
                ),
                PromptSuggestion(
                    id="suggest-quiz-recall",
                    title="Short Recall Questions",
                    prompt=(
                        f"Create short recall questions from this medical content for {audience_line}.\n\n"
                        "Return:\n"
                        "1. Question\n"
                        "2. Correct answer\n"
                        "3. Brief explanation grounded in the source\n"
                        f"{formatter_line}"
                    ),
                    rationale="Useful when you want quick active recall rather than full MCQs.",
                    category=inferred_category,
                    tags=["quiz", "recall", "revision"],
                ),
                PromptSuggestion(
                    id="suggest-quiz-mixed",
                    title="Mixed Revision Quiz",
                    prompt=(
                        f"Create a small revision quiz from this medical material for {audience_line}.\n\n"
                        "Include:\n"
                        "1. Multiple-choice items\n"
                        "2. One short-answer item\n"
                        "3. Brief explanations tied to the source\n"
                        f"{formatter_line}"
                    ),
                    rationale="Good for demos because it shows variety without changing the underlying task.",
                    category=inferred_category,
                    tags=["quiz", "mixed", "teaching"],
                ),
            ]

        return [
            PromptSuggestion(
                id="suggest-grounded-direct",
                title="Direct Grounded Prompt",
                prompt=(
                    f"Complete this medical learning task for {audience_line}.\n"
                    f"Task: {cleaned_task}\n\n"
                    "Return a direct answer that stays grounded in the available source material.\n"
                    f"{formatter_line}"
                ),
                rationale="Best for straightforward educational tasks tied to a document or selected source.",
                category=inferred_category,
                tags=["grounded", "direct", "study"],
            ),
            PromptSuggestion(
                id="suggest-grounded-structured",
                title="Structured Grounded Prompt",
                prompt=(
                    f"Handle this medical learning task for {audience_line}.\n"
                    f"Task: {cleaned_task}\n\n"
                    "Return:\n"
                    "1. Main answer\n"
                    "2. Supporting points\n"
                    "3. Any missing details or limits from the source\n"
                    f"{formatter_line}"
                ),
                rationale="Useful when you want a clean, presentation-friendly response shape.",
                category=inferred_category,
                tags=["grounded", "structured", "presentation"],
            ),
            PromptSuggestion(
                id="suggest-grounded-teaching",
                title="Teaching-Oriented Prompt",
                prompt=(
                    f"Answer this medical learning task so {audience_line} can reuse it for teaching or revision.\n"
                    f"Task: {cleaned_task}\n\n"
                    "Return:\n"
                    "1. Core explanation\n"
                    "2. Key supporting ideas\n"
                    "3. A short recap sentence\n"
                    f"{formatter_line}"
                ),
                rationale="Good when the response should feel class-ready instead of purely technical.",
                category=inferred_category,
                tags=["teaching", "revision", "recap"],
            ),
        ]

    @staticmethod
    def _build_actionable_improvement(
        prompt: str,
        *,
        inferred_category: str,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> str:
        lines = [normalize_whitespace(line) for line in prompt.splitlines() if normalize_whitespace(line)]
        formatter_line = PromptLibraryService._format_instruction(output_type, output_format)

        if inferred_category == "literature-search":
            preserved_lines = [
                line
                for line in lines
                if ":" in line and line.split(":", 1)[0].strip().lower() in {"research question", "population/topic", "topic", "goal", "audience"}
            ]
            if not preserved_lines:
                preserved_lines = [f"Topic or question: {normalize_whitespace(prompt)}"]
            bullets = "\n".join(f"- {line}" for line in preserved_lines)
            return (
                "Create a focused PubMed search strategy using the following inputs:\n"
                f"{bullets}\n\n"
                "Return:\n"
                "1. One concise PubMed-ready search query\n"
                "2. Important keywords or synonyms to include\n"
                "3. Optional filters or refinements that could improve relevance\n"
                f"{formatter_line}"
            ).strip()

        if inferred_category == "summarization":
            return (
                "Summarize the following medical material without changing its scope.\n"
                f"Task details:\n{prompt.strip()}\n\n"
                "Return:\n"
                "1. A short overview\n"
                "2. Key points\n"
                "3. Important caveats or missing details\n"
                f"{formatter_line}"
            ).strip()

        if inferred_category == "simplification":
            return (
                "Rewrite the following medical material in simpler language without adding new facts.\n"
                f"Task details:\n{prompt.strip()}\n\n"
                "Return:\n"
                "1. A plain-language explanation\n"
                "2. Short definitions for difficult terms only if they appear in the source\n"
                "3. A brief recap sentence\n"
                f"{formatter_line}"
            ).strip()

        if inferred_category == "assessment":
            return (
                "Create source-grounded revision questions from the following request.\n"
                f"Task details:\n{prompt.strip()}\n\n"
                "Return:\n"
                "1. Clear question text\n"
                "2. Answer or correct option\n"
                "3. Brief explanation tied to the source\n"
                f"{formatter_line}"
            ).strip()

        return (
            "Complete the following task while preserving its exact meaning.\n"
            f"Task:\n{prompt.strip()}\n\n"
            "Return:\n"
            "1. A direct response\n"
            "2. Clear structure that is easy to follow\n"
            "3. Explicit limits or missing information when needed\n"
            f"{formatter_line}"
        ).strip()

    @staticmethod
    def _format_instruction(output_type: PromptOutputType, output_format: PromptOutputFormat) -> str:
        if output_format == "structured_json":
            return "Format note: return the final response as structured JSON."
        if output_format == "structured_yaml":
            return "Format note: return the final response as structured YAML."
        return f"Format note: keep the final response in {output_type} form with a clean readable structure."

    @staticmethod
    def _category_changes(
        inferred_category: str,
        *,
        output_type: PromptOutputType,
        output_format: PromptOutputFormat,
    ) -> list[str]:
        base_changes = {
            "literature-search": "Converted the request into a PubMed-ready search prompt with explicit outputs.",
            "summarization": "Added a clear summary structure with overview, key points, and caveats.",
            "simplification": "Turned the request into a plain-language rewrite prompt without adding facts.",
            "assessment": "Added explicit revision-question structure tied to the source.",
        }
        changes = [base_changes.get(inferred_category, "Improved the prompt structure without changing the task.")]
        changes.append("Preserved the original intent and scope.")
        changes.append(f"Added target output type guidance ({output_type}).")
        changes.append(f"Added target output format guidance ({output_format}).")
        return changes
