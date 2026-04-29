from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Query, Request

from app.schemas.prompts import (
    PromptDetail,
    PromptImproveRequest,
    PromptImproveResponse,
    PromptSearchResult,
    PromptSuggestRequest,
    PromptSuggestResponse,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


@router.get("/search", response_model=list[PromptSearchResult])
def search_prompts(
    request: Request,
    query: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
) -> list[PromptSearchResult]:
    services = _get_services(request)
    return services.prompt_library_service.search_prompts(
        query=query,
        limit=limit,
        prompt_type=type,
        category=category,
        tag=tag,
    )


@router.post("/improve", response_model=PromptImproveResponse)
def improve_prompt(payload: PromptImproveRequest, request: Request) -> PromptImproveResponse:
    services = _get_services(request)
    return services.prompt_library_service.improve_prompt(
        prompt=payload.prompt,
        output_type=payload.output_type,
        output_format=payload.output_format,
    )


@router.post("/suggest", response_model=PromptSuggestResponse)
def suggest_prompt(payload: PromptSuggestRequest, request: Request) -> PromptSuggestResponse:
    services = _get_services(request)
    return services.prompt_library_service.suggest_prompts(
        task=payload.task,
        audience=payload.audience,
        mode_hint=payload.mode_hint,
        output_type=payload.output_type,
        output_format=payload.output_format,
    )


@router.get("/{prompt_id}", response_model=PromptDetail)
def get_prompt(prompt_id: str, request: Request) -> PromptDetail:
    services = _get_services(request)
    return services.prompt_library_service.get_prompt(prompt_id)
