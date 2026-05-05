from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.chat import AskRequest, AskResponse
from app.schemas.open_literature import OpenLiteratureSearchRequest
from app.services.rag_service import RetrievedChunk
from app.utils.text import normalize_whitespace, strip_unsafe_guidance

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


def _build_no_source_response(
    payload: AskRequest,
    safety,
    *,
    mode_used: str,
    enhanced_prompt: str | None = None,
) -> AskResponse:
    return AskResponse(
        status="no_source",
        mode_used=mode_used,
        answer="I could not find this answer in the uploaded documents.",
        safety=safety,
        sources=[],
        enhanced_prompt=enhanced_prompt,
        warnings=["The uploaded documents did not contain a useful matching passage for this request."],
    )


OUT_OF_SCOPE_ANSWER = (
    "This document appears to be outside MARA's medical education scope. "
    "MARA is designed for medical and health-learning content, so I can't summarize "
    "or generate quizzes from this source."
)
UNVERIFIED_SCOPE_ANSWER = (
    "This document has not been verified as medical or health-learning content, "
    "so MARA will not use it for medical workflows by default."
)


@router.post("/ask", response_model=AskResponse)
async def ask_question(payload: AskRequest, request: Request) -> AskResponse:
    services = _get_services(request)
    safety = services.safety_service.assess(payload.question)
    if not safety.allowed:
        return AskResponse(
            status="refused",
            mode_used="refuse",
            answer=services.safety_service.refusal_message(safety.category),
            safety=safety,
            warnings=["This assistant is educational only and not a clinical decision tool."],
        )
    base_warnings = []
    if safety.caution:
        base_warnings.append(safety.caution)

    mode = services.router_service.resolve_mode(
        payload.mode,
        payload.question,
        document_ids=payload.document_ids,
    )
    enhanced_prompt = None

    if mode == "prompt_enhance":
        enhanced_prompt = services.prompt_library_service.improve_prompt(
            prompt=payload.question,
            output_type="text",
            output_format="text",
        ).improved_prompt
        return AskResponse(
            status="ok",
            mode_used="prompt_enhance",
            answer="Prompt improved for clearer structure and execution without changing the original intent.",
            safety=safety,
            enhanced_prompt=enhanced_prompt,
        )

    if mode == "general_education":
        answer = services.general_education_service.answer(payload.question)
        answer, post_warnings, refused = _post_process_answer(services, answer)
        if refused:
            return AskResponse(
                status="refused",
                mode_used="refuse",
                answer=answer,
                safety=safety,
                warnings=base_warnings + post_warnings,
            )
        return AskResponse(
            status="ok",
            mode_used="general_education",
            answer=answer,
            safety=safety,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings
            + post_warnings
            + ["No uploaded documents were used. Use Open Literature or document RAG when you need grounded citations."],
        )

    if payload.enhance_prompt:
        base_enhanced_prompt = services.prompt_enhancer_service.enhance(payload.question, mode)
        enhanced_prompt = services.prompt_library_service.improve_prompt(
            prompt=base_enhanced_prompt,
            output_type="text",
            output_format="text",
        ).improved_prompt

    if mode == "pubmed":
        pubmed_results = services.pubmed_service.search(payload.question)
        answer = (
            f"Found {len(pubmed_results)} PubMed result(s) related to your query."
            if pubmed_results
            else "No PubMed records were found for this query."
        )
        warnings = []
        if pubmed_results:
            warnings.append(
                "PubMed search returns metadata cards here. You can select results and run summarize, compare, simplify, or quiz actions on abstracts or PMC full text."
            )
        return AskResponse(
            status="ok",
            mode_used="pubmed",
            answer=answer,
            safety=safety,
            pubmed_results=pubmed_results,
            enhanced_prompt=enhanced_prompt,
            warnings=warnings,
        )

    if mode == "open_literature":
        literature_response = services.open_literature_service.search(
            OpenLiteratureSearchRequest(query=payload.question)
        )
        return AskResponse(
            status="ok" if literature_response.status == "ok" else "no_source",
            mode_used="open_literature",
            answer=literature_response.answer or "No usable open literature sources were found.",
            safety=safety,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings + literature_response.warnings,
        )

    if mode == "open_article":
        return AskResponse(
            status="no_source",
            mode_used="open_article",
            answer="Open Article routing requires using the Open Article panel or endpoint so MARA can validate and import the URL safely.",
            safety=safety,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings + ["A URL was detected, but Assistant Lab does not import article URLs directly."],
        )

    scope_warnings: list[str] = []
    if mode in {"rag", "document_rag", "summarize", "simplify", "quiz"}:
        scope_state = _document_scope_state(services, payload.document_ids)
        scope_warnings = scope_state["warnings"]
        if not scope_state["has_records"] and not payload.document_ids:
            return _build_no_source_response(
                payload,
                safety,
                mode_used=mode,
                enhanced_prompt=enhanced_prompt,
            )
        if payload.document_ids and not scope_state["eligible_ids"] and scope_state["ineligible_count"]:
            answer = OUT_OF_SCOPE_ANSWER if scope_state["non_medical_count"] else UNVERIFIED_SCOPE_ANSWER
            return AskResponse(
                status="refused",
                mode_used=mode if mode in {"rag", "document_rag", "summarize", "simplify", "quiz"} else "refuse",
                answer=answer,
                safety=safety,
                enhanced_prompt=enhanced_prompt,
                warnings=base_warnings + scope_warnings,
            )
        if not payload.document_ids and not scope_state["eligible_ids"]:
            answer = (
                "No eligible medical documents are available for this workflow. "
                "MARA can only use uploaded sources that are medical, health-learning, or medical-adjacent."
            )
            return AskResponse(
                status="no_source",
                mode_used=mode,
                answer=answer,
                safety=safety,
                enhanced_prompt=enhanced_prompt,
                warnings=base_warnings + scope_warnings,
            )
        if not services.document_service.list_documents() and not payload.document_ids:
            return _build_no_source_response(
                payload,
                safety,
                mode_used=mode,
                enhanced_prompt=enhanced_prompt,
            )

    use_direct_document_context = mode in {"summarize", "simplify", "quiz"} and (
        bool(payload.document_ids) or services.router_service.references_uploaded_documents(payload.question.lower())
    )
    if _is_search_all_direct_workflow(services, payload, mode):
        response = _run_search_all_direct_workflow(
            services,
            payload,
            safety,
            mode=mode,
            scope_state=scope_state,
            base_warnings=base_warnings,
            scope_warnings=scope_warnings,
            enhanced_prompt=enhanced_prompt,
        )
        if response is not None:
            return response

    retrieved_chunks = _retrieve_document_chunks_for_chat(
        services,
        payload,
        use_direct_document_context=use_direct_document_context,
    )
    if not retrieved_chunks:
        return _build_no_source_response(
            payload,
            safety,
            mode_used=mode,
            enhanced_prompt=enhanced_prompt,
        )

    packed_context = services.rag_service.pack_context(retrieved_chunks)
    if not packed_context.text:
        response = _build_no_source_response(
            payload,
            safety,
            mode_used=mode,
            enhanced_prompt=enhanced_prompt,
        )
        response.warnings.append(
            "Matching passages were omitted because they contained treatment or medication dosing details."
        )
        return response

    sources = services.rag_service.to_source_refs(retrieved_chunks)
    if mode == "summarize":
        if use_direct_document_context:
            answer = services.summarization_service.summarize_context(
                payload.question,
                packed_context.text,
                enhanced_prompt=enhanced_prompt,
                context_label="Selected document context",
            )
        else:
            answer = services.summarization_service.summarize(
                payload.question, retrieved_chunks, enhanced_prompt=enhanced_prompt
            )
        answer, post_warnings, refused = _post_process_answer(services, answer)
        if refused:
            return AskResponse(
                status="refused",
                mode_used="refuse",
                answer=answer,
                safety=safety,
                sources=sources,
                warnings=base_warnings + post_warnings,
            )
        return AskResponse(
            status="ok",
            mode_used="summarize",
            answer=answer,
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings + scope_warnings + packed_context.warnings + post_warnings,
        )

    if mode == "simplify":
        if use_direct_document_context:
            answer = services.simplification_service.simplify_context(
                payload.question,
                packed_context.text,
                enhanced_prompt=enhanced_prompt,
                context_label="Selected document context",
            )
        else:
            answer = services.simplification_service.simplify(
                payload.question, retrieved_chunks, enhanced_prompt=enhanced_prompt
            )
        answer, post_warnings, refused = _post_process_answer(services, answer)
        if refused:
            return AskResponse(
                status="refused",
                mode_used="refuse",
                answer=answer,
                safety=safety,
                sources=sources,
                warnings=base_warnings + post_warnings,
            )
        return AskResponse(
            status="ok",
            mode_used="simplify",
            answer=answer,
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings + scope_warnings + packed_context.warnings + post_warnings,
        )

    if mode == "quiz":
        if use_direct_document_context:
            quiz_items = services.quiz_service.generate_context(
                payload.question,
                packed_context.text,
                enhanced_prompt=enhanced_prompt,
                context_label="Selected document context",
            )
        else:
            quiz_items = services.quiz_service.generate(
                payload.question, retrieved_chunks, enhanced_prompt=enhanced_prompt
            )
        return AskResponse(
            status="ok",
            mode_used="quiz",
            answer="Generated study questions from the uploaded medical documents.",
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
            quiz_items=quiz_items,
            warnings=base_warnings + scope_warnings + packed_context.warnings,
        )

    answer = services.answer_service.answer(
        payload.question,
        retrieved_chunks,
        enhanced_prompt=enhanced_prompt,
    )
    answer, post_warnings, refused = _post_process_answer(services, answer)
    grounding = services.grounding_service.check(answer, retrieved_chunks)
    grounding_warnings = [grounding.warning] if grounding.warning else []
    if refused:
        return AskResponse(
            status="refused",
            mode_used="refuse",
            answer=answer,
            safety=safety,
            sources=sources,
            warnings=base_warnings + post_warnings,
        )
    return AskResponse(
        status="ok",
        mode_used="document_rag" if mode == "document_rag" else "rag",
        answer=answer,
        safety=safety,
        sources=sources,
        enhanced_prompt=enhanced_prompt,
        warnings=base_warnings + scope_warnings + packed_context.warnings + post_warnings + grounding_warnings,
    )


def _post_process_answer(services: SimpleNamespace, answer: str) -> tuple[str, list[str], bool]:
    if not services.post_safety_service:
        return answer, [], False
    ok, findings = services.post_safety_service.check(answer)
    if ok:
        return answer, [], False
    return (
        services.post_safety_service.safe_replacement(),
        ["The generated answer was blocked by the post-generation safety checker."],
        True,
    )


def _is_search_all_direct_workflow(services: SimpleNamespace, payload: AskRequest, mode: str) -> bool:
    return (
        payload.document_ids is None
        and mode in {"summarize", "simplify", "quiz"}
        and services.router_service.references_uploaded_documents(payload.question.lower())
    )


def _run_search_all_direct_workflow(
    services: SimpleNamespace,
    payload: AskRequest,
    safety,
    *,
    mode: str,
    scope_state: dict,
    base_warnings: list[str],
    scope_warnings: list[str],
    enhanced_prompt: str | None,
) -> AskResponse | None:
    eligible_records = scope_state["eligible_records"]
    eligible_ids = [getattr(record, "document_id") for record in eligible_records if getattr(record, "document_id", None)]
    if not eligible_ids:
        answer = (
            "No eligible medical documents are available for this workflow. "
            "MARA can only use uploaded sources that are medical, health-learning, or medical-adjacent."
        )
        return AskResponse(
            status="no_source",
            mode_used=mode,
            answer=answer,
            safety=safety,
            enhanced_prompt=enhanced_prompt,
            warnings=base_warnings + scope_warnings,
        )

    chunks = _filter_registered_chunks(
        services,
        services.document_service.load_stored_document_chunks(document_ids=eligible_ids),
    )
    document_context, representative_chunks, workflow_warnings = _build_search_all_document_context(
        services,
        eligible_records,
        chunks,
    )
    if not document_context:
        return _build_no_source_response(
            payload,
            safety,
            mode_used=mode,
            enhanced_prompt=enhanced_prompt,
        )

    header = _build_search_all_inventory_header(scope_state, workflow_warnings)
    sources = services.rag_service.to_source_refs(representative_chunks)
    warnings = base_warnings + scope_warnings + workflow_warnings

    if mode == "summarize":
        answer = services.summarization_service.summarize_context(
            payload.question,
            document_context,
            enhanced_prompt=enhanced_prompt,
            context_label="Representative context from all eligible uploaded documents",
        )
        answer, post_warnings, refused = _post_process_answer(services, answer)
        if refused:
            return AskResponse(
                status="refused",
                mode_used="refuse",
                answer=answer,
                safety=safety,
                sources=sources,
                warnings=base_warnings + post_warnings,
            )
        return AskResponse(
            status="ok",
            mode_used="summarize",
            answer=f"{header}\n\n{answer}",
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
            warnings=warnings + post_warnings,
        )

    if mode == "simplify":
        answer = services.simplification_service.simplify_context(
            payload.question,
            document_context,
            enhanced_prompt=enhanced_prompt,
            context_label="Representative context from all eligible uploaded documents",
        )
        answer, post_warnings, refused = _post_process_answer(services, answer)
        if refused:
            return AskResponse(
                status="refused",
                mode_used="refuse",
                answer=answer,
                safety=safety,
                sources=sources,
                warnings=base_warnings + post_warnings,
            )
        return AskResponse(
            status="ok",
            mode_used="simplify",
            answer=f"{header}\n\n{answer}",
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
            warnings=warnings + post_warnings,
        )

    quiz_items = services.quiz_service.generate_context(
        payload.question,
        document_context,
        enhanced_prompt=enhanced_prompt,
        context_label="Representative context from all eligible uploaded documents",
    )
    return AskResponse(
        status="ok",
        mode_used="quiz",
        answer=f"{header}\n\nGenerated study questions from the eligible uploaded medical documents.",
        safety=safety,
        sources=sources,
        enhanced_prompt=enhanced_prompt,
        quiz_items=quiz_items,
        warnings=warnings,
    )


def _build_search_all_document_context(
    services: SimpleNamespace,
    eligible_records: list,
    chunks: list[RetrievedChunk],
) -> tuple[str, list[RetrievedChunk], list[str]]:
    grouped_chunks = _group_chunks_by_document(chunks)
    max_chars = max(int(getattr(services.rag_service.settings, "context_max_chars", 12000) or 12000), 3000)
    per_document_budget = max(1200, min(4000, max_chars // max(len(eligible_records), 1)))
    context_sections: list[str] = []
    representative_chunks: list[RetrievedChunk] = []
    warnings: list[str] = []

    for record in eligible_records:
        document_id = getattr(record, "document_id", "")
        filename = getattr(record, "filename", document_id or "document")
        document_chunks = grouped_chunks.get(document_id, [])
        if not document_chunks:
            warnings.append(f"No readable stored text was available for {filename}.")
            continue
        section, used_chunks, omitted_count = _representative_section_for_document(
            filename,
            document_chunks,
            max_chars=per_document_budget,
        )
        if not section:
            warnings.append(f"Readable text from {filename} was omitted by safety filtering.")
            continue
        context_sections.append(section)
        representative_chunks.extend(used_chunks)
        if omitted_count:
            warnings.append(
                f"{filename} was summarized from representative content; {omitted_count} chunk(s) were not included in the prompt budget."
            )

    return "\n\n".join(context_sections), representative_chunks, warnings


def _group_chunks_by_document(chunks: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        document_id = str(chunk.metadata.get("document_id", ""))
        if not document_id:
            continue
        grouped.setdefault(document_id, []).append(chunk)
    for document_chunks in grouped.values():
        document_chunks.sort(
            key=lambda chunk: (
                int(chunk.metadata.get("page", 0) or 0),
                str(chunk.metadata.get("chunk_id", "")),
            )
        )
    return grouped


def _representative_section_for_document(
    filename: str,
    chunks: list[RetrievedChunk],
    *,
    max_chars: int,
) -> tuple[str, list[RetrievedChunk], int]:
    parts = [f"Document: {filename}"]
    used_chunks: list[RetrievedChunk] = []
    current_chars = len(parts[0])
    for chunk in chunks:
        safe_text = normalize_whitespace(strip_unsafe_guidance(chunk.text))
        if not safe_text:
            continue
        page = int(chunk.metadata.get("page", 0) or 0) + 1
        chunk_id = str(chunk.metadata.get("chunk_id", "chunk"))
        block = f"[{filename}, page {page}, chunk {chunk_id}]\n{safe_text}"
        remaining = max_chars - current_chars - 2
        if remaining <= 0:
            break
        if len(block) > remaining:
            if used_chunks:
                break
            block = block[:remaining].rstrip()
        parts.append(block)
        used_chunks.append(chunk)
        current_chars += len(block) + 2
    omitted_count = max(len(chunks) - len(used_chunks), 0)
    return "\n\n".join(parts) if used_chunks else "", used_chunks, omitted_count


def _build_search_all_inventory_header(scope_state: dict, workflow_warnings: list[str]) -> str:
    lines = ["Included medical-scope documents:"]
    for record in scope_state["eligible_records"]:
        lines.append(f"- {getattr(record, 'filename', getattr(record, 'document_id', 'document'))}")
    if scope_state["ineligible_records"]:
        lines.append("")
        lines.append("Skipped out-of-scope or unverified documents:")
        for record in scope_state["ineligible_records"]:
            reason = getattr(record, "scope_reason", None) or getattr(record, "scope_category", "not verified")
            filename = getattr(record, "filename", getattr(record, "document_id", "document"))
            lines.append(f"- {filename} ({reason})")
    if workflow_warnings:
        lines.append("")
        lines.append("Coverage notes:")
        for warning in workflow_warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def _retrieve_document_chunks_for_chat(
    services: SimpleNamespace,
    payload: AskRequest,
    *,
    use_direct_document_context: bool,
) -> list[RetrievedChunk]:
    try:
        if use_direct_document_context:
            chunks = services.rag_service.retrieve_document_chunks(document_ids=payload.document_ids)
        else:
            chunks = services.rag_service.retrieve(
                payload.question,
                top_k=payload.top_k,
                document_ids=payload.document_ids,
            )
    except Exception:
        chunks = []

    chunks = _filter_registered_chunks(services, chunks)
    if chunks:
        return chunks

    if use_direct_document_context:
        return _filter_registered_chunks(
            services,
            services.document_service.load_stored_document_chunks(document_ids=payload.document_ids),
        )
    if services.router_service.references_uploaded_documents(payload.question.lower()):
        chunks = _filter_registered_chunks(
            services,
            services.document_service.load_stored_document_chunks(document_ids=payload.document_ids),
        )
        return _rank_fallback_chunks(payload.question, chunks, top_k=payload.top_k)
    return []


def _filter_registered_chunks(services: SimpleNamespace, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    try:
        state = _document_scope_state(services, None)
        if not state["has_records"]:
            return chunks
        known_ids = state["eligible_ids"]
    except Exception:
        return chunks
    return [
        chunk
        for chunk in chunks
        if str(chunk.metadata.get("document_id", "")) in known_ids
    ]


def _document_scope_state(services: SimpleNamespace, document_ids: list[str] | None) -> dict:
    records = services.document_service.list_documents()
    selected_ids = set(document_ids or [])
    scoped_records = [record for record in records if not selected_ids or getattr(record, "document_id", None) in selected_ids]
    eligible_records = [
        record
        for record in scoped_records
        if getattr(record, "eligible_for_medical_workflows", True)
    ]
    ineligible_records = [
        record
        for record in scoped_records
        if not getattr(record, "eligible_for_medical_workflows", True)
    ]
    non_medical_records = [
        record
        for record in ineligible_records
        if getattr(record, "scope_category", "unknown_unverified") == "non_medical"
    ]
    unverified_records = [
        record
        for record in ineligible_records
        if getattr(record, "scope_category", "unknown_unverified") in {"unknown", "unknown_unverified"}
    ]
    unknown_records = [
        record
        for record in eligible_records
        if getattr(record, "scope_category", "unknown") == "unknown"
        and hasattr(record, "eligible_for_medical_workflows")
    ]
    warnings: list[str] = []
    if ineligible_records:
        count = len(ineligible_records)
        warnings.append(f"Skipped {count} document{'s' if count != 1 else ''} because they are not verified as medical-scope sources.")
    if unknown_records:
        count = len(unknown_records)
        warnings.append(f"{count} document{'s have' if count != 1 else ' has'} unknown scope and will be used with caution.")
    return {
        "has_records": bool(scoped_records),
        "eligible_records": eligible_records,
        "ineligible_records": ineligible_records,
        "eligible_ids": {getattr(record, "document_id") for record in eligible_records if getattr(record, "document_id", None)},
        "ineligible_count": len(ineligible_records),
        "out_of_scope_count": len(ineligible_records),
        "non_medical_count": len(non_medical_records),
        "unverified_count": len(unverified_records),
        "unknown_count": len(unknown_records),
        "warnings": warnings,
    }


def _rank_fallback_chunks(question: str, chunks: list[RetrievedChunk], *, top_k: int) -> list[RetrievedChunk]:
    query_terms = {
        term
        for term in re.findall(r"[a-zA-Z][a-zA-Z]{3,}", question.lower())
        if term not in {"what", "does", "uploaded", "document", "about", "from", "this", "that", "with", "have"}
    }
    if not query_terms:
        return chunks[:top_k]
    scored = []
    for chunk in chunks:
        text = chunk.text.lower()
        overlap = sum(1 for term in query_terms if term in text)
        if overlap:
            scored.append(RetrievedChunk(text=chunk.text, metadata=chunk.metadata, score=float(overlap)))
    return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:top_k]
