from __future__ import annotations

from app.clients.ncbi_client import NCBIClient
from app.core.constants import PMC_URL_TEMPLATE
from app.schemas.open_article import OpenArticleSource
from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureFilters
from app.services.open_literature.adapters.base import ArticleSourceAdapter
from app.utils.text import clean_extracted_text


class PubMedMetadataAdapter(ArticleSourceAdapter):
    name = "pubmed"
    priority = 10

    def __init__(self, ncbi_client: NCBIClient) -> None:
        self.ncbi_client = ncbi_client

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        articles = self.ncbi_client.search_pubmed(query, limit=min(filters.max_results, 10))
        return [
            ArticleCandidate(
                title=article.title,
                authors=article.authors,
                year=article.publication_date,
                journal=article.journal,
                pmid=article.pmid,
                pmcid=article.pmcid,
                source=self.name,
                landing_page_url=article.pubmed_url,
                full_text_url=article.full_text_url,
                is_open_access=bool(article.pmcid),
                confidence_score=0.75 if article.pmcid else 0.55,
            )
            for article in articles
        ]

    def resolve(self, candidate: ArticleCandidate) -> ArticleResolution:
        status = "full_text" if candidate.pmcid else "abstract_only"
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.landing_page_url,
            full_text_url=candidate.full_text_url,
            pmc_xml_url=PMC_URL_TEMPLATE.format(pmcid=candidate.pmcid) if candidate.pmcid else None,
            source_priority=self.priority,
            license=candidate.license,
            full_text_status=status,
            warnings=[] if candidate.pmcid else ["PubMed record is treated as abstract/metadata unless full text is resolved elsewhere."],
        )

    def fetch_full_text(self, resolution: ArticleResolution) -> OpenArticleSource:
        candidate = resolution.candidate
        if candidate.pmcid:
            text = clean_extracted_text(self.ncbi_client.fetch_pmc_full_text(candidate.pmcid)).strip()
            if text:
                return OpenArticleSource(
                    title=candidate.title,
                    url=PMC_URL_TEMPLATE.format(pmcid=candidate.pmcid),
                    source_type="pmc_xml",
                    source_name="PubMed Central",
                    source_url=PMC_URL_TEMPLATE.format(pmcid=candidate.pmcid),
                    doi=candidate.doi,
                    pmid=candidate.pmid,
                    pmcid=candidate.pmcid,
                    authors=candidate.authors,
                    publication_date=candidate.year,
                    journal=candidate.journal,
                    license=resolution.license,
                    abstract=candidate.abstract,
                    body_text=text,
                    extraction_quality_score=0.95,
                    warnings=resolution.warnings,
                    full_text_status="full_text",
                    allowed_for_ai_processing=True,
                )
        return super().fetch_full_text(resolution)


class PMCOAAdapter(PubMedMetadataAdapter):
    name = "pmc_oa"
    priority = 1

    def search(self, query: str, filters: OpenLiteratureFilters) -> list[ArticleCandidate]:
        oa_query = f"({query}) AND pubmed pmc open access[filter]"
        candidates = super().search(oa_query, filters)
        for candidate in candidates:
            candidate.source = self.name
            candidate.is_open_access = True
            candidate.confidence_score = max(candidate.confidence_score, 0.9)
        return candidates
