from __future__ import annotations

from app.clients.ncbi_client import NCBIClient
from app.schemas.pubmed import PubMedArticle
from app.services.pubmed_service import PubMedService


def test_pubmed_mode_returns_metadata(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "search",
        lambda *args, **kwargs: [
            PubMedArticle(
                pmid="987654",
                title="Lung ultrasound education study",
                authors=["Jane Doe", "John Smith"],
                journal="Academic Medicine",
                publication_date="2025 Jan",
                pubmed_url="https://pubmed.ncbi.nlm.nih.gov/987654/",
            )
        ],
    )

    response = client.post(
        "/api/chat/ask",
        json={"question": "Search PubMed for lung ultrasound education.", "mode": "pubmed"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode_used"] == "pubmed"
    assert payload["pubmed_results"][0]["pmid"] == "987654"


def test_pubmed_query_normalization_removes_instructional_boilerplate():
    query = PubMedService._normalize_query(
        "Provide a list of relevant PubMed studies on Addison's disease, excluding studies on diagnosis, treatment, dosage, and triage, and focusing on educational content."
    )

    assert query == "Addison's disease"


def test_pubmed_query_normalization_handles_prompt_placeholders():
    query = PubMedService._normalize_query(
        "show me studies of medical content on ${chronic fatigue} from pubMED for ${audience:IT students}, providing a concise overview in a bullet list format with key points and any relevant caveats."
    )

    assert query == "chronic fatigue"


def test_pubmed_query_builder_adds_fielded_relevance_terms():
    query = PubMedService._build_search_query("anxiety")

    assert '"anxiety"[Title/Abstract]' in query
    assert '"anxiety"[MeSH Terms]' in query


def test_pubmed_search_uses_built_query_before_fallback():
    captured: list[tuple[str, int]] = []

    class StubNCBIClient:
        def search_pubmed(self, query: str, *, limit: int = 5):
            captured.append((query, limit))
            return []

    service = PubMedService(ncbi_client=StubNCBIClient())
    service.search("PubMed studies on anxiety", limit=4)

    assert captured[0][1] == 4
    assert '"anxiety"[Title/Abstract]' in captured[0][0]
    assert captured[1][0] == "anxiety"


def test_esearch_uses_relevance_sort(settings, monkeypatch):
    client = NCBIClient(settings)
    observed: dict[str, object] = {}

    def fake_get_json(endpoint: str, params: dict[str, object]) -> dict[str, object]:
        observed["endpoint"] = endpoint
        observed["params"] = params
        return {"esearchresult": {"idlist": []}}

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    client._esearch(query="anxiety", limit=5)

    assert observed["endpoint"] == "esearch.fcgi"
    assert observed["params"]["sort"] == "relevance"
