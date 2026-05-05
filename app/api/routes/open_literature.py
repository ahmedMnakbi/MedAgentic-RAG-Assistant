from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Request

from app.schemas.open_literature import (
    OpenLiteratureSearchRequest,
    OpenLiteratureSearchResponse,
    OpenLiteratureTransformRequest,
)

router = APIRouter(prefix="/open-literature", tags=["open literature"])


def _get_services(request: Request) -> SimpleNamespace:
    return request.app.state.services


@router.post("/search", response_model=OpenLiteratureSearchResponse)
def search_open_literature(
    payload: OpenLiteratureSearchRequest,
    request: Request,
) -> OpenLiteratureSearchResponse:
    services = _get_services(request)
    return services.open_literature_service.search(payload)


@router.post("/transform", response_model=OpenLiteratureSearchResponse)
def transform_open_literature(
    payload: OpenLiteratureTransformRequest,
    request: Request,
) -> OpenLiteratureSearchResponse:
    services = _get_services(request)
    search_payload = OpenLiteratureSearchRequest(
        query=payload.query,
        output_mode=payload.action,
    )
    search_payload.filters.full_text_required = payload.full_text_required
    return services.open_literature_service.search(search_payload)
