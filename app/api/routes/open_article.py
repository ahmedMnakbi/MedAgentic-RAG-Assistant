from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.open_article import (
    OpenArticleImportRequest,
    OpenArticleImportResponse,
    OpenArticleTransformRequest,
    OpenArticleTransformResponse,
)

router = APIRouter(prefix="/open-article", tags=["open article"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


@router.post("/import", response_model=OpenArticleImportResponse)
def import_open_article(payload: OpenArticleImportRequest, request: Request) -> OpenArticleImportResponse:
    services = _get_services(request)
    article = services.open_article_service.import_url(payload.url)
    status = "restricted" if article.full_text_status == "restricted" else "ok"
    return OpenArticleImportResponse(status=status, article=article, warnings=article.warnings)


@router.post("/transform", response_model=OpenArticleTransformResponse)
def transform_open_article(payload: OpenArticleTransformRequest, request: Request) -> OpenArticleTransformResponse:
    services = _get_services(request)
    article = payload.article or services.open_article_service.import_url(payload.url or "")
    if article.full_text_status == "restricted" or not article.allowed_for_ai_processing:
        return OpenArticleTransformResponse(
            status="restricted",
            action=payload.action,
            answer="This source is not clearly allowed for automatic AI ingestion. Use a PMC Open Access version or another clearly reusable source when available.",
            article=article,
            warnings=article.warnings,
        )

    question = payload.question or _default_question(payload.action)
    safety = services.safety_service.assess(question)
    if not safety.allowed:
        return OpenArticleTransformResponse(
            status="refused",
            action=payload.action,
            answer=services.safety_service.refusal_message(safety.category),
            article=article,
            warnings=["This assistant is educational only and not a clinical decision tool."],
        )

    context = services.open_article_service.build_context(article, max_chars=12000)
    if not context:
        return OpenArticleTransformResponse(
            status="no_source",
            action=payload.action,
            answer="I could not extract enough readable article text to complete this request.",
            article=article,
            warnings=article.warnings,
        )

    enhanced_prompt = None
    if payload.enhance_prompt:
        enhanced_prompt = services.prompt_enhancer_service.enhance(question, payload.action)

    if payload.action == "simplify":
        answer = services.simplification_service.simplify_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Imported open article context",
        )
        return _safe_response(services, payload.action, answer, article)

    if payload.action in {"quiz", "exam_questions"}:
        quiz_items = services.quiz_service.generate_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Imported open article context",
        )
        return OpenArticleTransformResponse(
            status="ok",
            action=payload.action,
            answer="Generated study questions from the imported open article.",
            article=article,
            quiz_items=[item.model_dump() for item in quiz_items],
            warnings=article.warnings,
        )

    if payload.action == "summarize":
        answer = services.summarization_service.summarize_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Imported open article context",
        )
    else:
        answer = services.answer_service.answer_context(
            question,
            context,
            enhanced_prompt=enhanced_prompt,
            context_label="Imported open article context",
        )
    return _safe_response(services, payload.action, answer, article)


def _default_question(action: str) -> str:
    mapping = {
        "summarize": "Summarize this open article for medical students.",
        "simplify": "Explain this open article in simpler educational language.",
        "quiz": "Create study quiz questions from this open article.",
        "compare": "Compare this article with selected literature sources when available.",
        "extract_key_claims": "Extract key educational claims from this article with source-aware wording.",
        "extract_limitations": "Extract the study limitations from this article.",
        "extract_pico": "Extract PICO elements when present in this article.",
        "citation_card": "Create a citation card for this article.",
        "study_notes": "Create student study notes from this article.",
        "exam_questions": "Create exam-style questions from this article.",
        "extract_methodology": "Extract methodology details from this article.",
    }
    return mapping.get(action, mapping["summarize"])


def _safe_response(services: SimpleNamespace, action: str, answer: str, article) -> OpenArticleTransformResponse:
    ok, _ = services.post_safety_service.check(answer)
    if not ok:
        return OpenArticleTransformResponse(
            status="refused",
            action=action,
            answer=services.post_safety_service.safe_replacement(),
            article=article,
            warnings=article.warnings + ["The generated answer was blocked by the post-generation safety checker."],
        )
    return OpenArticleTransformResponse(
        status="ok",
        action=action,
        answer=answer,
        article=article,
        warnings=article.warnings,
    )
