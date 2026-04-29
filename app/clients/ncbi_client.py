from __future__ import annotations

import html
from typing import Any

import httpx

from app.core.config import Settings
from app.core.constants import PUBMED_URL_TEMPLATE
from app.core.exceptions import ExternalServiceError, NotConfiguredError
from app.schemas.pubmed import PubMedArticle
from app.utils.text import clean_extracted_text


class NCBIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def search_pubmed(self, query: str, *, limit: int = 5) -> list[PubMedArticle]:
        if not self.settings.ncbi_email:
            raise NotConfiguredError("NCBI_EMAIL must be configured before PubMed search can be used.")

        id_list = self._esearch(query=query, limit=limit)
        if not id_list:
            return []
        summary_payload = self._esummary(id_list)
        result = summary_payload.get("result", {})
        articles: list[PubMedArticle] = []
        for pmid in id_list:
            item = result.get(pmid)
            if not item:
                continue
            authors = [entry.get("name", "").strip() for entry in item.get("authors", []) if entry.get("name")]
            articles.append(
                PubMedArticle(
                    pmid=pmid,
                    title=clean_extracted_text(html.unescape(item.get("title", "")).strip()),
                    authors=[clean_extracted_text(author) for author in authors],
                    journal=clean_extracted_text(
                        html.unescape(item.get("fulljournalname") or item.get("source") or "").strip()
                    ),
                    publication_date=clean_extracted_text(str(item.get("pubdate", "")).strip()),
                    pubmed_url=PUBMED_URL_TEMPLATE.format(pmid=pmid),
                )
            )
        return articles

    def _esearch(self, *, query: str, limit: int) -> list[str]:
        payload = self._get_json(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": limit,
                **self._base_params(),
            },
        )
        return payload.get("esearchresult", {}).get("idlist", [])

    def _esummary(self, pmids: list[str]) -> dict[str, Any]:
        return self._get_json(
            "esummary.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
                **self._base_params(),
            },
        )

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.pubmed_base_url}/{endpoint}"
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError("PubMed metadata search failed.") from exc

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "tool": self.settings.ncbi_tool,
            "email": self.settings.ncbi_email,
        }
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key.get_secret_value()
        return params
