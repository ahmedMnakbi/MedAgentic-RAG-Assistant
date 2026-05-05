from __future__ import annotations

from urllib.parse import urlparse

import pytest

from app.core.exceptions import AppError
from app.services.open_article_service import OpenArticleService


def _html(body: str) -> str:
    return f"""
    <html>
      <head>
        <title>Readable medical article</title>
        <meta name="citation_doi" content="10.1234/example" />
      </head>
      <body>
        <article>
          <h1>Readable medical article</h1>
          <h2>Abstract</h2>
          <p>{body}</p>
          <h2>Discussion</h2>
          <p>{body}</p>
        </article>
      </body>
    </html>
    """


def test_open_article_rejects_localhost():
    with pytest.raises(AppError):
        OpenArticleService.validate_public_url("http://127.0.0.1:8000/private")


def test_open_article_extracts_readable_html(settings, monkeypatch):
    service = OpenArticleService(settings=settings, ncbi_client=object())
    body = "This article explains sepsis pathophysiology for education only. " * 25
    monkeypatch.setattr(service, "validate_public_url", lambda url: urlparse(url))
    monkeypatch.setattr(service, "_fetch_html", lambda url: _html(body))

    article = service.import_url("https://example.org/article")

    assert article.full_text_status == "full_text"
    assert article.extraction_quality_score > 0.2
    assert article.doi == "10.1234/example"
    assert article.sections


def test_open_article_rejects_too_short_pages(settings, monkeypatch):
    service = OpenArticleService(settings=settings, ncbi_client=object())
    monkeypatch.setattr(service, "validate_public_url", lambda url: urlparse(url))
    monkeypatch.setattr(service, "_fetch_html", lambda url: _html("Too short."))

    with pytest.raises(AppError):
        service.import_url("https://example.org/short")


def test_open_article_cureus_is_restricted_by_default(settings, monkeypatch):
    service = OpenArticleService(settings=settings, ncbi_client=object())
    monkeypatch.setattr(service, "validate_public_url", lambda url: urlparse(url))

    article = service.import_url("https://www.cureus.com/articles/123-test")

    assert article.full_text_status == "restricted"
    assert article.allowed_for_ai_processing is False
    assert any("Cureus" in warning for warning in article.warnings)


def test_open_article_transform_endpoint_uses_service(client, app, monkeypatch):
    body = "This article explains renal physiology for education only. " * 25
    article_service = app.state.services.open_article_service
    monkeypatch.setattr(article_service, "validate_public_url", lambda url: urlparse(url))
    monkeypatch.setattr(article_service, "_fetch_html", lambda url: _html(body))
    monkeypatch.setattr(
        app.state.services.summarization_service,
        "summarize_context",
        lambda *args, **kwargs: "Educational article summary.",
    )

    response = client.post(
        "/api/open-article/transform",
        json={"url": "https://example.org/article", "action": "summarize"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["answer"] == "Educational article summary."
