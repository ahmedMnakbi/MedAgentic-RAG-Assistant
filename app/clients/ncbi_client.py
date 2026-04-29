from __future__ import annotations

import html
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.core.config import Settings
from app.core.constants import PMC_IDCONVERTER_URL, PMC_URL_TEMPLATE, PUBMED_URL_TEMPLATE
from app.core.exceptions import ExternalServiceError, NotConfiguredError
from app.schemas.pubmed import PubMedArticle
from app.utils.text import clean_extracted_text, normalize_whitespace


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
        pmcid_map = self.resolve_pmcids(id_list)
        articles: list[PubMedArticle] = []
        for pmid in id_list:
            item = result.get(pmid)
            if not item:
                continue
            authors = [entry.get("name", "").strip() for entry in item.get("authors", []) if entry.get("name")]
            pmcid = pmcid_map.get(pmid)
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
                    pmcid=pmcid,
                    full_text_url=PMC_URL_TEMPLATE.format(pmcid=pmcid) if pmcid else None,
                    content_availability="pmc_full_text" if pmcid else "abstract_only",
                )
            )
        return articles

    def fetch_pubmed_details(self, pmids: list[str]) -> dict[str, dict[str, str]]:
        if not pmids:
            return {}
        xml_payload = self._get_text(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                **self._base_params(),
            },
        )
        return self._parse_pubmed_details(xml_payload)

    def resolve_pmcids(self, pmids: list[str]) -> dict[str, str]:
        if not pmids:
            return {}
        payload = self._get_json_absolute(
            PMC_IDCONVERTER_URL,
            {
                "ids": ",".join(pmids),
                "format": "json",
                **self._base_params(),
            },
        )
        mapping: dict[str, str] = {}
        for record in payload.get("records", []):
            pmid = str(record.get("pmid") or "").strip()
            pmcid = str(record.get("pmcid") or "").strip()
            if pmid and pmcid:
                mapping[pmid] = pmcid
        return mapping

    def fetch_pmc_full_text(self, pmcid: str) -> str:
        article_id = pmcid.replace("PMC", "", 1).strip()
        if not article_id:
            return ""
        xml_payload = self._get_text(
            "efetch.fcgi",
            {
                "db": "pmc",
                "id": article_id,
                "retmode": "xml",
                **self._base_params(),
            },
        )
        return self._parse_pmc_full_text(xml_payload)

    def _esearch(self, *, query: str, limit: int) -> list[str]:
        payload = self._get_json(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": limit,
                "sort": "relevance",
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
        return self._get_json_absolute(f"{self.settings.pubmed_base_url}/{endpoint}", params)

    def _get_json_absolute(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=20.0) as client:
                for attempt in range(3):
                    response = client.get(url, params=params)
                    if response.status_code == 429 and attempt < 2:
                        time.sleep(1.0 + attempt)
                        continue
                    response.raise_for_status()
                    return response.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError("PubMed metadata search failed.") from exc
        raise ExternalServiceError("PubMed metadata search failed.")

    def _get_text(self, endpoint: str, params: dict[str, Any]) -> str:
        url = f"{self.settings.pubmed_base_url}/{endpoint}"
        try:
            with httpx.Client(timeout=25.0) as client:
                for attempt in range(3):
                    response = client.get(url, params=params)
                    if response.status_code == 429 and attempt < 2:
                        time.sleep(1.0 + attempt)
                        continue
                    response.raise_for_status()
                    return response.text
        except httpx.HTTPError as exc:
            raise ExternalServiceError("PubMed content retrieval failed.") from exc
        raise ExternalServiceError("PubMed content retrieval failed.")

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "tool": self.settings.ncbi_tool,
            "email": self.settings.ncbi_email,
        }
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key.get_secret_value()
        return params

    @staticmethod
    def _parse_pubmed_details(xml_payload: str) -> dict[str, dict[str, str]]:
        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as exc:
            raise ExternalServiceError("PubMed content retrieval returned invalid XML.") from exc

        records: dict[str, dict[str, str]] = {}
        for article in root.findall(".//PubmedArticle"):
            pmid = normalize_whitespace("".join(article.findtext(".//MedlineCitation/PMID", default="")))
            if not pmid:
                continue

            title_node = article.find(".//Article/ArticleTitle")
            title = normalize_whitespace(" ".join(title_node.itertext())) if title_node is not None else ""

            journal = normalize_whitespace(
                article.findtext(".//Article/Journal/Title", default="")
                or article.findtext(".//Article/Journal/ISOAbbreviation", default="")
            )

            pubdate_parts = [
                article.findtext(".//Article/Journal/JournalIssue/PubDate/Year", default=""),
                article.findtext(".//Article/Journal/JournalIssue/PubDate/Month", default=""),
                article.findtext(".//Article/Journal/JournalIssue/PubDate/Day", default=""),
            ]
            publication_date = normalize_whitespace(" ".join(part for part in pubdate_parts if part))

            abstract_parts: list[str] = []
            for abstract_node in article.findall(".//Abstract/AbstractText"):
                part = normalize_whitespace(" ".join(abstract_node.itertext()))
                if not part:
                    continue
                label = normalize_whitespace(abstract_node.attrib.get("Label", ""))
                if label and not part.lower().startswith(label.lower()):
                    part = f"{label}: {part}"
                abstract_parts.append(part)

            records[pmid] = {
                "pmid": pmid,
                "title": clean_extracted_text(title),
                "journal": clean_extracted_text(journal),
                "publication_date": clean_extracted_text(publication_date),
                "abstract": clean_extracted_text("\n\n".join(abstract_parts)),
                "pubmed_url": PUBMED_URL_TEMPLATE.format(pmid=pmid),
            }
        return records

    @staticmethod
    def _parse_pmc_full_text(xml_payload: str) -> str:
        try:
            root = ET.fromstring(xml_payload)
        except ET.ParseError as exc:
            raise ExternalServiceError("PMC full-text retrieval returned invalid XML.") from exc

        parts: list[str] = []
        seen: set[str] = set()

        for abstract_node in root.findall(".//abstract//p"):
            text = normalize_whitespace(" ".join(abstract_node.itertext()))
            if text and text not in seen:
                seen.add(text)
                parts.append(text)

        for paragraph_node in root.findall(".//body//p"):
            text = normalize_whitespace(" ".join(paragraph_node.itertext()))
            if len(text) < 40 or text in seen:
                continue
            seen.add(text)
            parts.append(text)

        if not parts:
            body_node = root.find(".//body")
            if body_node is not None:
                fallback = normalize_whitespace(" ".join(body_node.itertext()))
                if fallback:
                    parts.append(fallback)

        return clean_extracted_text("\n\n".join(parts))
