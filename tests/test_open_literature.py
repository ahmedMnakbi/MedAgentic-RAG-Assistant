from __future__ import annotations

from app.schemas.open_article import OpenArticleSource
from app.schemas.open_literature import ArticleCandidate, ArticleResolution, OpenLiteratureSearchRequest
from app.services.open_literature.adapters.base import ArticleSourceAdapter
from app.services.open_literature.adapters.cureus_adapter import CureusAdapter
from app.services.open_literature.deduplication_service import LiteratureDeduplicationService
from app.services.open_literature.search_service import OpenLiteratureSearchService
from app.services.safety_service import SafetyService


class FakeFullTextAdapter(ArticleSourceAdapter):
    name = "fake_full_text"
    priority = 1

    def search(self, query, filters):
        return [
            ArticleCandidate(
                title="Full text sepsis review",
                doi="10.1/full",
                source=self.name,
                landing_page_url="https://example.org/full",
                full_text_url="https://example.org/full",
                is_open_access=True,
                confidence_score=0.9,
            )
        ]

    def resolve(self, candidate):
        return ArticleResolution(
            candidate=candidate,
            resolved_url=candidate.full_text_url,
            full_text_url=candidate.full_text_url,
            full_text_status="full_text",
            license="https://creativecommons.org/licenses/by/4.0/",
            source_priority=self.priority,
        )

    def fetch_full_text(self, resolution):
        return OpenArticleSource(
            title=resolution.candidate.title,
            url=resolution.resolved_url or "",
            source_type=self.name,
            source_name=self.name,
            doi=resolution.candidate.doi,
            body_text="Sepsis pathophysiology full text for educational synthesis. " * 20,
            extraction_quality_score=0.8,
            full_text_status="full_text",
            allowed_for_ai_processing=True,
        )


class FakeAbstractAdapter(ArticleSourceAdapter):
    name = "fake_abstract"
    priority = 2

    def search(self, query, filters):
        return [
            ArticleCandidate(
                title="Abstract only sepsis record",
                doi="10.1/abstract",
                abstract="Abstract text only.",
                source=self.name,
                landing_page_url="https://example.org/abstract",
                confidence_score=0.5,
            )
        ]


def test_open_literature_source_adapter_interface(settings):
    adapter = FakeFullTextAdapter()
    candidate = adapter.search("sepsis", OpenLiteratureSearchRequest(query="sepsis").filters)[0]
    resolution = adapter.resolve(candidate)
    source = adapter.fetch_full_text(resolution)

    assert candidate.title
    assert resolution.full_text_status == "full_text"
    assert source.full_text_status == "full_text"


def test_open_literature_search_counts_statuses(settings):
    service = OpenLiteratureSearchService(
        settings=settings,
        safety_service=SafetyService(),
        adapters=[FakeFullTextAdapter(), FakeAbstractAdapter()],
    )

    result = service.search(OpenLiteratureSearchRequest(query="sepsis pathophysiology"))

    assert result.status == "ok"
    assert result.candidate_count == 2
    assert result.full_text_count == 1
    assert result.abstract_only_count == 1
    assert result.selected_sources[0].full_text_status == "full_text"
    assert result.evidence_table


def test_open_literature_full_text_required_excludes_abstract_only(settings):
    service = OpenLiteratureSearchService(
        settings=settings,
        safety_service=SafetyService(),
        adapters=[FakeAbstractAdapter()],
    )
    request = OpenLiteratureSearchRequest(query="sepsis")
    request.filters.full_text_required = True

    result = service.search(request)

    assert result.status == "no_source"
    assert result.selected_sources == []
    assert result.abstract_only_count == 1


def test_open_literature_deduplicates_by_doi():
    candidates = [
        ArticleCandidate(title="A", doi="10.1/x", source="one", confidence_score=0.2),
        ArticleCandidate(title="A better", doi="10.1/x", source="two", full_text_url="https://example.org", confidence_score=0.9),
    ]

    deduped = LiteratureDeduplicationService().deduplicate(candidates)

    assert len(deduped) == 1
    assert deduped[0].full_text_url


def test_cureus_adapter_marks_restricted():
    candidate = ArticleCandidate(title="Cureus case", source="cureus", landing_page_url="https://www.cureus.com/articles/1")

    resolution = CureusAdapter().resolve(candidate)

    assert resolution.full_text_status == "restricted"
    assert resolution.warnings


def test_open_literature_endpoint_works_with_mocked_service(client, app, monkeypatch):
    service = OpenLiteratureSearchService(
        settings=app.state.settings,
        safety_service=SafetyService(),
        adapters=[FakeFullTextAdapter()],
    )
    monkeypatch.setattr(app.state.services, "open_literature_service", service)

    response = client.post("/api/open-literature/search", json={"query": "sepsis"})

    assert response.status_code == 200
    assert response.json()["full_text_count"] == 1
