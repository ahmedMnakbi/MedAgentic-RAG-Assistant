from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.pubmed import (
    PubMedTransformRequest,
    PubMedTransformResponse,
    PubMedUrlTransformRequest,
)

router = APIRouter(prefix="/pubmed", tags=["pubmed"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


def _enhance_prompt(services: SimpleNamespace, question: str, mode: str, enabled: bool) -> str | None:
    if not enabled:
        return None
    base_enhanced_prompt = services.prompt_enhancer_service.enhance(question, mode)
    return services.prompt_library_service.improve_prompt(
        prompt=base_enhanced_prompt,
        output_type="text",
        output_format="text",
    ).improved_prompt


def _run_action(
    services: SimpleNamespace,
    *,
    action: str,
    question: str,
    context: str,
    enhanced_prompt: str | None,
):
    if action == "summarize":
        return services.summarization_service.summarize_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Selected PubMed article context",
        )
    if action == "simplify":
        return services.simplification_service.simplify_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Selected PubMed article context",
        )
    quiz_items = services.quiz_service.generate_context(
        question,
        context,
        enhanced_prompt=enhanced_prompt,
        context_label="Selected PubMed article context",
    )
    return quiz_items


@router.post("/transform", response_model=PubMedTransformResponse)
def transform_selected_articles(payload: PubMedTransformRequest, request: Request) -> PubMedTransformResponse:
    services = _get_services(request)
    question = payload.question or services.pubmed_service.default_question(
        payload.action,
        source_count=len(payload.pmids),
    )
    safety = services.safety_service.assess(question)
    if not safety.allowed:
        return PubMedTransformResponse(
            status="refused",
            action=payload.action,
            answer=services.safety_service.refusal_message(safety.category),
            safety=safety,
            warnings=["This assistant is educational only and not a clinical decision tool."],
        )

    enhanced_prompt = _enhance_prompt(services, question, payload.action, payload.enhance_prompt)
    sources, warnings = services.pubmed_service.collect_selected_sources(
        payload.pmids,
        prefer_full_text=payload.prefer_full_text,
    )
    context = services.pubmed_service.build_context(sources)
    if not context:
        return PubMedTransformResponse(
            status="no_source",
            action=payload.action,
            answer="I could not load enough PubMed article content to complete this request.",
            safety=safety,
            selected_sources=[source.to_selected_source() for source in sources],
            enhanced_prompt=enhanced_prompt,
            warnings=warnings
            or ["No usable abstract or PMC full text could be loaded for the selected PubMed article(s)."],
        )

    result = _run_action(
        services,
        action=payload.action,
        question=question,
        context=context,
        enhanced_prompt=enhanced_prompt,
    )
    if payload.action == "quiz":
        for item in result:
            if not item.source_titles:
                item.source_titles = [source.title for source in sources]
        return PubMedTransformResponse(
            status="ok",
            action=payload.action,
            answer="Generated study quiz questions from the selected PubMed source(s).",
            safety=safety,
            selected_sources=[source.to_selected_source() for source in sources],
            enhanced_prompt=enhanced_prompt,
            quiz_items=result,
            warnings=warnings,
        )

    return PubMedTransformResponse(
        status="ok",
        action=payload.action,
        answer=result,
        safety=safety,
        selected_sources=[source.to_selected_source() for source in sources],
        enhanced_prompt=enhanced_prompt,
        warnings=warnings,
    )


@router.post("/import-url", response_model=PubMedTransformResponse)
def transform_open_access_url(payload: PubMedUrlTransformRequest, request: Request) -> PubMedTransformResponse:
    services = _get_services(request)
    question = payload.question or services.pubmed_service.default_question(payload.action, source_count=1)
    safety = services.safety_service.assess(question)
    if not safety.allowed:
        return PubMedTransformResponse(
            status="refused",
            action=payload.action,
            answer=services.safety_service.refusal_message(safety.category),
            safety=safety,
            warnings=["This assistant is educational only and not a clinical decision tool."],
        )

    enhanced_prompt = _enhance_prompt(services, question, payload.action, payload.enhance_prompt)
    source = services.pubmed_service.import_open_access_url(payload.url)
    context = services.pubmed_service.build_context([source])
    if not context:
        return PubMedTransformResponse(
            status="no_source",
            action=payload.action,
            answer="I could not extract enough readable open-access article text to complete this request.",
            safety=safety,
            selected_sources=[source.to_selected_source()],
            enhanced_prompt=enhanced_prompt,
            warnings=["The imported article text could not be used after safety filtering."],
        )

    result = _run_action(
        services,
        action=payload.action,
        question=question,
        context=context,
        enhanced_prompt=enhanced_prompt,
    )
    if payload.action == "quiz":
        for item in result:
            if not item.source_titles:
                item.source_titles = [source.title]
        return PubMedTransformResponse(
            status="ok",
            action=payload.action,
            answer="Generated study quiz questions from the imported open-access article.",
            safety=safety,
            selected_sources=[source.to_selected_source()],
            enhanced_prompt=enhanced_prompt,
            quiz_items=result,
            warnings=["Open-access URL import is experimental and may not work on every site."],
        )

    return PubMedTransformResponse(
        status="ok",
        action=payload.action,
        answer=result,
        safety=safety,
        selected_sources=[source.to_selected_source()],
        enhanced_prompt=enhanced_prompt,
        warnings=["Open-access URL import is experimental and may not work on every site."],
    )
