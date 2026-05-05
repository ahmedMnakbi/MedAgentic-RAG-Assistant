from __future__ import annotations

import httpx

from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class CrossrefAdapter(ArticleSourceAdapter):
    name = "crossref"
    priority = 7
    base_url = "https://api.crossref.org/works"

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        try:
            response = httpx.get(
                self.base_url,
                params={"query": query, "rows": min(filters.max_results, 10)},
                timeout=15.0,
            )
            response.raise_for_status()
            items = response.json().get("message", {}).get("items", [])
        except Exception:
            return []
        candidates: list[ArticleCandidate] = []
        for item in items:
            license_items = item.get("license") or []
            link_items = item.get("link") or []
            candidates.append(
                ArticleCandidate(
                    title=(item.get("title") or ["Untitled Crossref record"])[0],
                    authors=[
                        " ".join(filter(None, [author.get("given"), author.get("family")]))
                        for author in item.get("author", [])
                    ],
                    year=str(((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[""]])[0][0]),
                    journal=(item.get("container-title") or [None])[0],
                    abstract=item.get("abstract"),
                    doi=item.get("DOI"),
                    source=self.name,
                    landing_page_url=item.get("URL"),
                    full_text_url=next((link.get("URL") for link in link_items if link.get("content-type") in {"text/html", "application/pdf"}), None),
                    license=(license_items[0] or {}).get("URL") if license_items else None,
                    is_open_access=bool(license_items),
                    confidence_score=0.55,
                )
            )
        return candidates

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "metadata_only"
        warnings = ["Crossref is used for metadata, license, DOI, and link enrichment, not as proof of full-text ingestion."]
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
            warnings=warnings,
        )
