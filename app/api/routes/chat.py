from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.chat import AskRequest, AskResponse
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

    mode = services.router_service.resolve_mode(payload.mode, payload.question)
    enhanced_prompt = None

    if payload.enhance_prompt or mode == "prompt_enhance":
        enhanced_prompt = services.prompt_enhancer_service.enhance(payload.question, mode)
        if mode == "prompt_enhance":
            return AskResponse(
                status="ok",
                mode_used="prompt_enhance",
                answer="Prompt enhanced for structured educational use without changing the original intent.",
                safety=safety,
                enhanced_prompt=enhanced_prompt,
            )

    if mode == "pubmed":
        pubmed_results = services.pubmed_service.search(payload.question)
        answer = (
            f"Found {len(pubmed_results)} PubMed result(s) related to your query."
            if pubmed_results
            else "No PubMed records were found for this query."
        )
        warnings = []
        if pubmed_results:
            warnings.append("PubMed results are metadata-only in v1.")
        return AskResponse(
            status="ok",
            mode_used="pubmed",
            answer=answer,
            safety=safety,
            pubmed_results=pubmed_results,
            enhanced_prompt=enhanced_prompt,
            warnings=warnings,
        )

    retrieved_chunks: list[RetrievedChunk] = services.rag_service.retrieve(
        payload.question,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )
    if not retrieved_chunks:
        return _build_no_source_response(
            payload,
            safety,
            mode_used=mode,
            enhanced_prompt=enhanced_prompt,
        )

    sources = services.rag_service.to_source_refs(retrieved_chunks)
    if mode == "summarize":
        answer = services.summarization_service.summarize(
            payload.question, retrieved_chunks, enhanced_prompt=enhanced_prompt
        )
        return AskResponse(
            status="ok",
            mode_used="summarize",
            answer=answer,
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
        )

    if mode == "simplify":
        answer = services.simplification_service.simplify(
            payload.question, retrieved_chunks, enhanced_prompt=enhanced_prompt
        )
        return AskResponse(
            status="ok",
            mode_used="simplify",
            answer=answer,
            safety=safety,
            sources=sources,
            enhanced_prompt=enhanced_prompt,
        )

    if mode == "quiz":
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
        )

    answer = services.answer_service.answer(
        payload.question,
        retrieved_chunks,
        enhanced_prompt=enhanced_prompt,
    )
    return AskResponse(
        status="ok",
        mode_used="rag",
        answer=answer,
        safety=safety,
        sources=sources,
        enhanced_prompt=enhanced_prompt,
    )
