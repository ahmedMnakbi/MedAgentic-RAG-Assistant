from __future__ import annotations

from urllib.parse import urlparse

from app.core.config import Settings
from app.schemas.open_literature import ArticleResolution


class LicensePolicyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def allowed(self, resolution: ArticleResolution) -> tuple[bool, str | None]:
        url = resolution.resolved_url or resolution.full_text_url or ""
        hostname = (urlparse(url).hostname or "").lower()
        blocked = {
            item.strip().lower()
            for item in self.settings.open_literature_blocked_domains.split(",")
            if item.strip()
        }
        if hostname in blocked:
            return False, "Source domain is blocked by configuration."
        if "cureus.com" in hostname and not self.settings.open_literature_enable_cureus_experimental:
            return False, "Cureus is restricted/link-only unless experimental ingestion is explicitly enabled."
        if resolution.full_text_status != "full_text":
            return False, "Source is not full text."
        license_text = (resolution.license or "").lower()
        if not license_text:
            return True, "No machine-readable license was found; use with caution and keep warnings visible."
        if any(token in license_text for token in ("creativecommons", "cc-by", "cc by", "cc0", "publicdomain")):
            return True, None
        return True, "License is not a standard machine-readable Creative Commons value; keep source warnings visible."
