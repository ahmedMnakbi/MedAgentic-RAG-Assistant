from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

router = APIRouter(tags=["web"])


@router.get("/", include_in_schema=False)
def serve_web_app() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
