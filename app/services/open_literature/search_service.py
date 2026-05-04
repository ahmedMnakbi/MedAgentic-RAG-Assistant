from __future__ import annotations

from collections import Counter

from app.core.config import Settings
from app.schemas.open_article import OpenArticleSource
from app.schemas.open_literature import (
    ArticleCandidate,
    ArticleResolution,
    EvidenceTableRow,
    OpenLiteratureSearchRequest,
    OpenLiteratureSearchResponse,
)
from app.services.open_literature.adapters.base import ArticleSourceAdapter
from app.services.open_literature.adapters.generic_html_adapter import GenericOAHTMLAdapter
from app.services.open_literature.deduplication_service import LiteratureDeduplicationService
from app.services.open_literature.extraction_quality_service import ExtractionQualityService
from app.services.open_literature.license_policy_service import LicensePolicyService
from app.services.safety_service import SafetyService
from app.utils.text import normalize_whitespace, to_excerpt


class OpenLiteratureSearchService:
    def __init__(
        self,
        *,
        settings: Settings,
        safety_service: SafetyService,
        adapters: list[ArticleSourceAdapter],
        generic_adapter: GenericOAHTMLAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.safety_service = safety_service
        self.adapters = sorted(adapters, key=lambda adapter: adapter.priority)
        self.generic_adapter = generic_adapter
        self.deduper = LiteratureDeduplicationService()
        self.license_policy = LicensePolicyService(settings)
        self.quality = ExtractionQualityService()

    def search(self, request: OpenLiteratureSearchRequest) -> OpenLiteratureSearchResponse:
        safety = self.safety_service.assess(request.query)
        if not safety.allowed:
            return OpenLiteratureSearchResponse(
                status="refused",
                query=request.query,
                safety=safety,
                answer=self.safety_service.refusal_message(safety.category),
                warnings=["Open Literature is educational only and cannot handle unsafe clinical requests."],
            )

        filters = request.filters
        if filters.full_text_required is None:
            filters.full_text_required = self.settings.open_literature_require_full_text_default
        query_variants = self._query_variants(request.query)
        candidates: list[ArticleCandidate] = []
        sources_searched: list[str] = []
        for adapter in self.adapters:
            sources_searched.append(adapter.name)
            for query in query_variants:
                try:
                    candidates.extend(adapter.search(query, filters))
                except Exception:
                    continue
        candidates = self.deduper.deduplicate(candidates)[: self.settings.open_literature_max_candidates]
        resolutions: list[ArticleResolution] = []
        selected_sources: list[OpenArticleSource] = []
        warnings: list[str] = []

        adapter_map = {adapter.name: adapter for adapter in self.adapters}
        for candidate in candidates:
            adapter = adapter_map.get(candidate.source)
            if adapter is None:
                continue
            resolution = adapter.resolve(candidate)
            allowed, policy_warning = self.license_policy.allowed(resolution)
            if policy_warning:
                resolution.warnings.append(policy_warning)
            if filters.full_text_required and resolution.full_text_status != "full_text":
                resolution.warnings.append("Excluded from selected evidence because full_text_required is true.")
            resolutions.append(resolution)
            if not allowed and filters.full_text_required:
                warnings.extend(resolution.warnings)
                continue
            if resolution.full_text_status == "restricted":
                warnings.extend(resolution.warnings)
                continue
            source = self._fetch_source(adapter, resolution)
            source.extraction_quality_score = self.quality.score(source)
            if filters.full_text_required and source.full_text_status != "full_text":
                continue
            if source.full_text_status == "full_text" and len(source.body_text) < 250:
                source.full_text_status = "extraction_failed"
                source.allowed_for_ai_processing = False
                source.warnings.append("Full-text extraction was too short to use.")
            selected_sources.append(source)

        counts = Counter(resolution.full_text_status for resolution in resolutions)
        answer = self._answer(request.query, selected_sources, filters.full_text_required or False, counts)
        evidence_table = self._evidence_table(selected_sources)
        status = "ok" if candidates else "no_source"
        if candidates and not selected_sources and filters.full_text_required:
            status = "no_source"
            warnings.append("Candidates were found, but none had usable full text under the current policy.")
        return OpenLiteratureSearchResponse(
            status=status,
            query=request.query,
            search_strategy=[
                "Generated query variants.",
                "Searched trusted metadata and open-access sources.",
                "Deduplicated DOI/PMID/PMCID/title matches.",
                "Selected usable sources only after full-text/status checks.",
            ],
            query_variants=query_variants,
            sources_searched=sources_searched,
            candidates=candidates,
            resolutions=resolutions,
            selected_sources=selected_sources,
            answer=answer,
            evidence_table=evidence_table,
            safety=safety,
            warnings=list(dict.fromkeys(warnings + [warning for source in selected_sources for warning in source.warnings])),
            candidate_count=len(candidates),
            full_text_count=counts["full_text"],
            abstract_only_count=counts["abstract_only"],
            metadata_only_count=counts["metadata_only"],
            restricted_count=counts["restricted"] + counts["extraction_failed"],
        )

    def _fetch_source(self, adapter: ArticleSourceAdapter, resolution: ArticleResolution) -> OpenArticleSource:
        try:
            source = adapter.fetch_full_text(resolution)
            if source.full_text_status == "full_text" and len(source.body_text) >= 250:
                return source
        except Exception:
            pass
        if self.generic_adapter and (resolution.full_text_url or resolution.resolved_url):
            try:
                return self.generic_adapter.fetch_full_text(resolution)
            except Exception:
                pass
        return adapter.fetch_full_text(resolution)

    @staticmethod
    def _query_variants(query: str) -> list[str]:
        cleaned = normalize_whitespace(query)
        variants = [cleaned]
        if "pathophysiology" in cleaned.lower():
            variants.append(f"{cleaned} review mechanism")
        if "full text" not in cleaned.lower():
            variants.append(f"{cleaned} open access full text")
        if "case report" not in cleaned.lower() and any(term in cleaned.lower() for term in ("qtc", "crisis", "rare")):
            variants.append(f"{cleaned} case report")
        return list(dict.fromkeys(variants))

    @staticmethod
    def _answer(query: str, sources: list[OpenArticleSource], full_text_required: bool, counts: Counter) -> str:
        if not sources:
            return (
                "No usable full-text sources were available for this request."
                if full_text_required
                else "No usable open literature sources were selected for synthesis."
            )
        source_lines = []
        for index, source in enumerate(sources[:5], start=1):
            status = source.full_text_status
            excerpt = to_excerpt(source.body_text or source.abstract or "", max_length=180)
            source_lines.append(f"{index}. {source.title} ({status}) - {excerpt}")
        return (
            f"Search summary for: {query}\n\n"
            f"Full text available: {counts['full_text']}; abstract only: {counts['abstract_only']}; "
            f"metadata only: {counts['metadata_only']}; restricted/rejected: {counts['restricted'] + counts['extraction_failed']}.\n\n"
            "Selected source highlights:\n"
            + "\n".join(source_lines)
            + "\n\nEducational safety note: this synthesis is for learning only and does not provide diagnosis, dosage, triage, or personalized treatment advice."
        )

    @staticmethod
    def _evidence_table(sources: list[OpenArticleSource]) -> list[EvidenceTableRow]:
        rows = []
        for source in sources[:8]:
            rows.append(
                EvidenceTableRow(
                    article=source.title,
                    study_type=None,
                    population=None,
                    intervention_or_exposure=None,
                    outcome=None,
                    main_finding=to_excerpt(source.body_text or source.abstract or "", max_length=220),
                    source_status=source.full_text_status,
                    citation=source.pmcid or source.pmid or source.doi or source.source_url or source.url,
                )
            )
        return rows
