from __future__ import annotations

import httpx

from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters
from app.services.open_literature.adapters.base import ArticleSourceAdapter


class EuropePMCAdapter(ArticleSourceAdapter):
    name = "europe_pmc"
    priority = 3
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        try:
            response = httpx.get(
                self.base_url,
                params={"query": query, "format": "json", "pageSize": min(filters.max_results, 10)},
                timeout=15.0,
            )
            response.raise_for_status()
            items = response.json().get("resultList", {}).get("result", [])
        except Exception:
            return []
        candidates: list[ArticleCandidate] = []
        for item in items:
            pmcid = item.get("pmcid")
            full_text_url = f"https://europepmc.org/articles/{pmcid}" if pmcid and item.get("isOpenAccess") == "Y" else None
            candidates.append(
                ArticleCandidate(
                    title=item.get("title") or "Untitled Europe PMC record",
                    authors=[item.get("authorString", "")] if item.get("authorString") else [],
                    year=item.get("pubYear"),
                    journal=item.get("journalTitle"),
                    abstract=item.get("abstractText"),
                    doi=item.get("doi"),
                    pmid=item.get("pmid"),
                    pmcid=pmcid,
                    source=self.name,
                    landing_page_url=f"https://europepmc.org/article/MED/{item.get('pmid')}" if item.get("pmid") else None,
                    full_text_url=full_text_url,
                    license=item.get("license"),
                    is_open_access=item.get("isOpenAccess") == "Y",
                    confidence_score=0.85 if full_text_url else 0.6,
                )
            )
        return candidates

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "full_text" if candidate.full_text_url else "abstract_only" if candidate.abstract else "metadata_only"
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.full_text_url or candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
            warnings=[] if status == "full_text" else ["Europe PMC did not expose usable full text for this candidate."],
        )
