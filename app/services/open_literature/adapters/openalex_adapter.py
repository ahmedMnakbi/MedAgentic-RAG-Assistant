from __future__ import annotations

import httpx

from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class OpenAlexAdapter(ArticleSourceAdapter):
    name = "openalex"
    priority = 5
    base_url = "https://api.openalex.org/works"

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        params = {"search": query, "per-page": min(filters.max_results, 10)}
        if filters.open_access_only:
            params["filter"] = "is_oa:true"
        try:
            response = httpx.get(self.base_url, params=params, timeout=15.0)
            response.raise_for_status()
            items = response.json().get("results", [])
        except Exception:
            return []
        candidates: list[ArticleCandidate] = []
        for item in items:
            oa = item.get("open_access") or {}
            best = item.get("best_oa_location") or {}
            ids = item.get("ids") or {}
            authors = [
                (authorship.get("author") or {}).get("display_name", "")
                for authorship in item.get("authorships", [])
                if (authorship.get("author") or {}).get("display_name")
            ]
            candidates.append(
                ArticleCandidate(
                    title=item.get("display_name") or "Untitled OpenAlex work",
                    authors=authors,
                    year=str(item.get("publication_year") or ""),
                    journal=((item.get("primary_location") or {}).get("source") or {}).get("display_name"),
                    doi=(ids.get("doi") or "").replace("https://doi.org/", "") or None,
                    pmid=(ids.get("pmid") or "").rsplit("/", 1)[-1] if ids.get("pmid") else None,
                    pmcid=(ids.get("pmcid") or "").rsplit("/", 1)[-1] if ids.get("pmcid") else None,
                    source=self.name,
                    landing_page_url=item.get("primary_location", {}).get("landing_page_url"),
                    full_text_url=oa.get("oa_url") or best.get("landing_page_url"),
                    pdf_url=best.get("pdf_url"),
                    license=best.get("license"),
                    is_open_access=bool(oa.get("is_oa")),
                    confidence_score=0.8 if oa.get("is_oa") else 0.45,
                )
            )
        return candidates

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "full_text" if candidate.full_text_url or candidate.pdf_url else "metadata_only"
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.full_text_url or candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            pdf_url=candidate.pdf_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
            warnings=[] if status == "full_text" else ["OpenAlex enriched metadata but did not provide a readable OA location."],
        )
