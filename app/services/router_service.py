from __future__ import annotations

from app.core.constants import DEFAULT_ROUTER_MODE, ROUTER_KEYWORDS


class RouterService:
    def resolve_mode(self, requested_mode: str, question: str) -> str:
        if requested_mode != "auto":
            return requested_mode

        lowered = question.lower()
        for mode, keywords in ROUTER_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return mode
        return DEFAULT_ROUTER_MODE
