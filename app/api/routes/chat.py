from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.chat import AskRequest, AskResponse
from app.schemas.open_literature import OpenLiteratureSearchRequest
from app.services.rag_service import RetrievedChunk

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

    if mode in {"rag", "document_rag", "summarize", "simplify", "quiz"} and not payload.document_ids:
        if not services.document_service.list_documents():
            return _build_no_source_response(
                payload,
                safety,
                mode_used=mode,
                enhanced_prompt=enhanced_prompt,
            )

    use_selected_document_context = bool(payload.document_ids) and mode in {"summarize", "simplify", "quiz"}
    retrieved_chunks = _retrieve_document_chunks_for_chat(
        services,
        payload,
        use_full_selected_context=use_selected_document_context,
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
        if use_selected_document_context:
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
            warnings=base_warnings + packed_context.warnings + post_warnings,
        )

    if mode == "simplify":
        if use_selected_document_context:
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
            warnings=base_warnings + packed_context.warnings + post_warnings,
        )

    if mode == "quiz":
        if use_selected_document_context:
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
            warnings=base_warnings + packed_context.warnings,
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
        warnings=base_warnings + packed_context.warnings + post_warnings + grounding_warnings,
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


def _retrieve_document_chunks_for_chat(
    services: SimpleNamespace,
    payload: AskRequest,
    *,
    use_full_selected_context: bool,
) -> list[RetrievedChunk]:
    try:
        if use_full_selected_context:
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

    if use_full_selected_context:
        return services.document_service.load_stored_document_chunks(document_ids=payload.document_ids)
    if services.router_service.references_uploaded_documents(payload.question.lower()):
        chunks = services.document_service.load_stored_document_chunks(document_ids=payload.document_ids)
        return _rank_fallback_chunks(payload.question, chunks, top_k=payload.top_k)
    return []


def _filter_registered_chunks(services: SimpleNamespace, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    try:
        known_ids = {
            document_id
            for document_id in (
                getattr(document, "document_id", None)
                for document in services.document_service.list_documents()
            )
            if document_id
        }
    except Exception:
        return chunks
    return [
        chunk
        for chunk in chunks
        if str(chunk.metadata.get("document_id", "")) in known_ids
    ]


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
