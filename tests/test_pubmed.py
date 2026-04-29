from __future__ import annotations

from urllib.parse import urlparse

import pytest

from app.clients.ncbi_client import NCBIClient
from app.core.exceptions import AppError
from app.schemas.common import QuizItem
from app.schemas.pubmed import PubMedArticle
from app.services.pubmed_service import PubMedContextSource, PubMedService
from app.services.quiz_service import QuizService


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
                pmcid="PMC987654",
                full_text_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC987654/",
                content_availability="pmc_full_text",
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
    assert payload["pubmed_results"][0]["pmcid"] == "PMC987654"


def test_transform_selected_pubmed_articles_returns_summary(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "collect_selected_sources",
        lambda *args, **kwargs: (
            [
                PubMedContextSource(
                    title="War Anxiety: A Review.",
                    text="Anxiety is discussed for study purposes only.",
                    source_type="abstract_only",
                    source_url="https://pubmed.ncbi.nlm.nih.gov/39738916/",
                    pmid="39738916",
                )
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        app.state.services.summarization_service,
        "summarize_context",
        lambda *args, **kwargs: "Summary from selected PubMed article.",
    )

    response = client.post(
        "/api/pubmed/transform",
        json={"pmids": ["39738916"], "action": "summarize"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["action"] == "summarize"
    assert payload["answer"] == "Summary from selected PubMed article."
    assert payload["selected_sources"][0]["pmid"] == "39738916"


def test_transform_selected_pubmed_articles_compare_returns_merged_answer(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "collect_selected_sources",
        lambda *args, **kwargs: (
            [
                PubMedContextSource(
                    title="Study A",
                    text="Source A.",
                    source_type="abstract_only",
                    source_url="https://pubmed.ncbi.nlm.nih.gov/1/",
                    pmid="1",
                ),
                PubMedContextSource(
                    title="Study B",
                    text="Source B.",
                    source_type="abstract_only",
                    source_url="https://pubmed.ncbi.nlm.nih.gov/2/",
                    pmid="2",
                ),
                PubMedContextSource(
                    title="Study C",
                    text="Source C.",
                    source_type="abstract_only",
                    source_url="https://pubmed.ncbi.nlm.nih.gov/3/",
                    pmid="3",
                ),
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        app.state.services.summarization_service,
        "compare_context",
        lambda *args, **kwargs: "Merged comparison across selected studies.",
    )

    response = client.post(
        "/api/pubmed/transform",
        json={"pmids": ["1", "2", "3"], "action": "compare"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "Merged comparison across selected studies."


def test_transform_selected_pubmed_articles_compare_requires_multiple_pmids(client):
    response = client.post(
        "/api/pubmed/transform",
        json={"pmids": ["39738916"], "action": "compare"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
    assert "3 to 5" in payload["answer"]


def test_transform_selected_pubmed_articles_populates_quiz_source_titles(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "collect_selected_sources",
        lambda *args, **kwargs: (
            [
                PubMedContextSource(
                    title="Digital Media, Anxiety, and Depression in Children.",
                    text="Source text for quiz generation.",
                    source_type="abstract_only",
                    source_url="https://pubmed.ncbi.nlm.nih.gov/29093037/",
                    pmid="29093037",
                )
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        app.state.services.quiz_service,
        "generate_context",
        lambda *args, **kwargs: [
            QuizItem(
                question="What is the study about?",
                options=["A", "B"],
                correct_answer="A",
                explanation="Because the source says so.",
                source_pages=[],
            )
        ],
    )

    response = client.post(
        "/api/pubmed/transform",
        json={"pmids": ["29093037"], "action": "quiz"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quiz_items"][0]["source_titles"] == [
        "Digital Media, Anxiety, and Depression in Children."
    ]


def test_open_access_url_transform_uses_imported_source(client, app, monkeypatch):
    monkeypatch.setattr(
        app.state.services.pubmed_service,
        "import_open_access_url",
        lambda *args, **kwargs: PubMedContextSource(
            title="Open access article",
            text="Open access full text for study purposes.",
            source_type="open_access_url",
            source_url="https://example.org/article",
        ),
    )
    monkeypatch.setattr(
        app.state.services.simplification_service,
        "simplify_context",
        lambda *args, **kwargs: "Simplified from imported article.",
    )

    response = client.post(
        "/api/pubmed/import-url",
        json={"url": "https://example.org/article", "action": "simplify"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "Simplified from imported article."
    assert payload["selected_sources"][0]["source_type"] == "open_access_url"


def test_open_access_url_compare_is_rejected(client):
    response = client.post(
        "/api/pubmed/import-url",
        json={"url": "https://example.org/article", "action": "compare"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_source"
    assert "not available for a single imported url" in payload["answer"].lower()


def test_transform_selected_pubmed_articles_refuses_unsafe_request(client):
    response = client.post(
        "/api/pubmed/transform",
        json={
            "pmids": ["39738916"],
            "action": "summarize",
            "question": "Is 50mg steroids a good dosage for Addison's disease?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["safety"]["category"] == "unsafe_dosage"


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


def test_pubmed_service_rejects_localhost_import_url():
    service = PubMedService(ncbi_client=object())

    with pytest.raises(AppError):
        service.import_open_access_url("http://127.0.0.1:8000/private")


def test_fit_sources_for_compare_trims_large_context():
    service = PubMedService(ncbi_client=object())
    sources = [
        PubMedContextSource(
            title="Study A",
            text="A" * 7000,
            source_type="abstract_only",
            source_url="https://pubmed.ncbi.nlm.nih.gov/1/",
            pmid="1",
        ),
        PubMedContextSource(
            title="Study B",
            text="B" * 7000,
            source_type="abstract_only",
            source_url="https://pubmed.ncbi.nlm.nih.gov/2/",
            pmid="2",
        ),
        PubMedContextSource(
            title="Study C",
            text="C" * 7000,
            source_type="abstract_only",
            source_url="https://pubmed.ncbi.nlm.nih.gov/3/",
            pmid="3",
        ),
    ]

    trimmed = service.fit_sources_for_action(sources, action="compare")

    assert all(len(item.text) <= 3203 for item in trimmed)


def test_import_open_access_url_uses_official_pmc_path(monkeypatch):
    class StubNCBIClient:
        def fetch_pmc_full_text(self, pmcid: str) -> str:
            assert pmcid == "PMC7106568"
            return "Full PMC text " * 40

    service = PubMedService(ncbi_client=StubNCBIClient())
    monkeypatch.setattr(service, "_validate_public_url", lambda url: urlparse(url))

    source = service.import_open_access_url("https://pmc.ncbi.nlm.nih.gov/articles/PMC7106568/")

    assert source.source_type == "pmc_full_text"
    assert source.pmcid == "PMC7106568"


def test_esearch_uses_relevance_sort(settings, monkeypatch):
    client = NCBIClient(settings)
    observed: dict[str, object] = {}

    def fake_get_json_absolute(url: str, params: dict[str, object]) -> dict[str, object]:
        observed["url"] = url
        observed["params"] = params
        return {"esearchresult": {"idlist": []}}

    monkeypatch.setattr(client, "_get_json_absolute", fake_get_json_absolute)

    client._esearch(query="anxiety", limit=5)

    assert observed["url"].endswith("/esearch.fcgi")
    assert observed["params"]["sort"] == "relevance"


def test_parse_pubmed_details_extracts_abstract():
    xml_payload = """<?xml version='1.0'?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345</PMID>
          <Article>
            <ArticleTitle>Test Title</ArticleTitle>
            <Journal>
              <Title>Test Journal</Title>
              <JournalIssue>
                <PubDate><Year>2024</Year><Month>Oct</Month></PubDate>
              </JournalIssue>
            </Journal>
            <Abstract>
              <AbstractText Label='Background'>First part.</AbstractText>
              <AbstractText>Second part.</AbstractText>
            </Abstract>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>"""

    payload = NCBIClient._parse_pubmed_details(xml_payload)

    assert payload["12345"]["title"] == "Test Title"
    assert "Background: First part." in payload["12345"]["abstract"]
    assert "Second part." in payload["12345"]["abstract"]


def test_parse_pmc_full_text_extracts_body_paragraphs():
    xml_payload = """<?xml version='1.0'?>
    <pmc-articleset>
      <article>
        <front>
          <article-meta>
            <abstract><p>Abstract overview paragraph for students.</p></abstract>
          </article-meta>
        </front>
        <body>
          <sec><p>This is a full text paragraph with enough content for extraction.</p></sec>
          <sec><p>This is another body paragraph with additional information for context.</p></sec>
        </body>
      </article>
    </pmc-articleset>"""

    content = NCBIClient._parse_pmc_full_text(xml_payload)

    assert "Abstract overview paragraph for students." in content
    assert "This is another body paragraph with additional information for context." in content


def test_quiz_service_adds_missing_correct_answer_to_options():
    class StubGroqClient:
        def generate_json(self, *args, **kwargs):
            return [
                {
                    "question": "What is the reported threshold?",
                    "options": ["10%", "12%", "15%"],
                    "correct_answer": "Below 13%",
                    "explanation": "The study reported values below 13%.",
                    "source_pages": [2],
                }
            ]

    service = QuizService(groq_client=StubGroqClient())
    items = service.generate_context("Create a quiz.", "Context")

    assert items[0].correct_answer in items[0].options
