from __future__ import annotations

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
