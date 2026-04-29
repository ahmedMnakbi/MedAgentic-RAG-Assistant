from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.clients.ncbi_client import NCBIClient
from app.core.constants import PMC_URL_TEMPLATE
from app.core.exceptions import AppError, ExternalServiceError
from app.schemas.pubmed import PubMedArticle, PubMedSelectedSource
from app.utils.text import clean_extracted_text, normalize_whitespace, strip_unsafe_guidance, to_excerpt

PROMPT_PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}]+)\}")
NON_TOPIC_PLACEHOLDER_KEYS = {
    "audience",
    "format",
    "style",
    "tone",
    "length",
    "output",
    "goal",
}
HTML_PARAGRAPH_SELECTORS = (
    "article p",
    "main p",
    "[role='main'] p",
    ".article p",
    ".article__body p",
    ".content p",
    ".main-content p",
)


@dataclass(slots=True)
class PubMedContextSource:
    title: str
    text: str
    source_type: Literal["abstract_only", "pmc_full_text", "open_access_url"]
    source_url: str
    pmid: str | None = None
    pmcid: str | None = None

    def to_selected_source(self) -> PubMedSelectedSource:
        return PubMedSelectedSource(
            title=self.title,
            excerpt=to_excerpt(self.text),
            source_type=self.source_type,
            source_url=self.source_url,
            pmid=self.pmid,
            pmcid=self.pmcid,
        )


class PubMedService:
    def __init__(self, *, ncbi_client: NCBIClient) -> None:
        self.ncbi_client = ncbi_client

    def search(self, question: str, *, limit: int = 5) -> list[PubMedArticle]:
        topic = self._normalize_query(question)
        if not topic:
            return []
        primary_query = self._build_search_query(topic)
        articles = self.ncbi_client.search_pubmed(primary_query, limit=limit)
        if articles:
            return articles
        if primary_query != topic:
            return self.ncbi_client.search_pubmed(topic, limit=limit)
        return []

    def collect_selected_sources(
        self,
        pmids: list[str],
        *,
        prefer_full_text: bool = True,
    ) -> tuple[list[PubMedContextSource], list[str]]:
        details = self.ncbi_client.fetch_pubmed_details(pmids)
        pmcid_map = self.ncbi_client.resolve_pmcids(pmids)
        warnings: list[str] = []
        sources: list[PubMedContextSource] = []

        for pmid in pmids:
            record = details.get(pmid)
            if not record:
                warnings.append(f"No PubMed content could be loaded for PMID {pmid}.")
                continue

            title = record.get("title") or f"PMID {pmid}"
            pmcid = pmcid_map.get(pmid)
            full_text = ""
            if prefer_full_text and pmcid:
                try:
                    full_text = self.ncbi_client.fetch_pmc_full_text(pmcid)
                except ExternalServiceError:
                    warnings.append(f"PMC full text could not be loaded for PMID {pmid}; abstract fallback was used.")
                else:
                    full_text = self._truncate_context(full_text)

            if full_text:
                sources.append(
                    PubMedContextSource(
                        title=title,
                        text=full_text,
                        source_type="pmc_full_text",
                        source_url=PMC_URL_TEMPLATE.format(pmcid=pmcid),
                        pmid=pmid,
                        pmcid=pmcid,
                    )
                )
                continue

            abstract = self._truncate_context(record.get("abstract", ""))
            if abstract:
                sources.append(
                    PubMedContextSource(
                        title=title,
                        text=abstract,
                        source_type="abstract_only",
                        source_url=record.get("pubmed_url", ""),
                        pmid=pmid,
                        pmcid=pmcid,
                    )
                )
                if pmcid and prefer_full_text:
                    warnings.append(
                        f"PMC full text for PMID {pmid} was unavailable or too short, so the abstract was used instead."
                    )
                continue

            warnings.append(f"No abstract or usable full text was available for PMID {pmid}.")

        return sources, warnings

    def import_open_access_url(self, url: str) -> PubMedContextSource:
        parsed = self._validate_public_url(url)
        pmcid = self._extract_pmcid_from_url(parsed.geturl())
        if pmcid:
            full_text = self._truncate_context(self.ncbi_client.fetch_pmc_full_text(pmcid))
            if len(full_text) < 250:
                raise AppError(
                    "The PMC article did not expose enough readable full text to use for study generation.",
                    code="article_text_unavailable",
                    status_code=400,
                )
            return PubMedContextSource(
                title=f"PMC article {pmcid}",
                text=full_text,
                source_type="pmc_full_text",
                source_url=parsed.geturl(),
                pmcid=pmcid,
            )

        html_payload = self._fetch_html(parsed.geturl())
        title, text = self._extract_article_text(html_payload)
        cleaned_text = self._truncate_context(text)
        if len(cleaned_text) < 250:
            raise AppError(
                "The article URL did not expose enough readable open-access text to use for study generation.",
                code="article_text_unavailable",
                status_code=400,
            )
        return PubMedContextSource(
            title=title or parsed.geturl(),
            text=cleaned_text,
            source_type="open_access_url",
            source_url=parsed.geturl(),
        )

    @staticmethod
    def build_context(sources: list[PubMedContextSource]) -> str:
        parts = []
        for source in sources:
            safe_text = strip_unsafe_guidance(source.text)
            if not safe_text:
                continue
            label = f"{source.title}"
            if source.pmid:
                label += f" | PMID {source.pmid}"
            if source.pmcid:
                label += f" | {source.pmcid}"
            label += f" | Source: {source.source_type}"
            parts.append(f"[PubMed Source: {label}]\n{safe_text}")
        return "\n\n".join(parts)

    @staticmethod
    def default_question(action: str, *, source_count: int) -> str:
        noun = "article" if source_count == 1 else "articles"
        if action == "summarize":
            return f"Summarize the selected PubMed {noun} for educational study purposes."
        if action == "simplify":
            return f"Explain the selected PubMed {noun} in simpler educational language."
        return f"Create study quiz questions from the selected PubMed {noun}."

    @staticmethod
    def _normalize_query(question: str) -> str:
        cleaned = PubMedService._replace_prompt_placeholders(question.strip())
        cleaned = re.sub(
            r",?\s*(excluding|without)\s+.+?(?=,\s*(and\s+)?focusing\b|[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r",?\s*(and\s+)?focusing\s+on\s+.+?(?=[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r",?\s*(providing|with|including)\s+.+?(?=[.?!;]|$)",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        topic_match = re.search(
            r"\b(?:on|about|regarding)\s+(.+?)(?=\s+from\b|,\s*|[.?!;]|$)",
            cleaned,
            flags=re.IGNORECASE,
        )
        if topic_match:
            cleaned = topic_match.group(1)

        cleaned = re.sub(
            r"\b("
            r"pubmed|ncbi|papers|paper|studies|study|articles|article|"
            r"provide|list|relevant|find|show|give|return|search|results?|"
            r"please|me|metadata|educational|content|medical|overview|bullet|format|"
            r"key|points|caveats"
            r")\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9)']+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+,", ",", cleaned).strip(" ,")
        return cleaned

    @staticmethod
    def _build_search_query(topic: str) -> str:
        cleaned_topic = re.sub(r"\s+", " ", topic).strip()
        if not cleaned_topic:
            return ""
        escaped_topic = cleaned_topic.replace('"', "")
        return f"(\"{escaped_topic}\"[Title/Abstract] OR \"{escaped_topic}\"[MeSH Terms] OR {escaped_topic})"

    @staticmethod
    def _replace_prompt_placeholders(question: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            inner = match.group(1).strip()
            if ":" not in inner:
                return inner
            key, value = inner.split(":", 1)
            if key.strip().lower() in NON_TOPIC_PLACEHOLDER_KEYS:
                return " "
            return value.strip()

        return PROMPT_PLACEHOLDER_PATTERN.sub(_replace, question)

    @staticmethod
    def _truncate_context(text: str, *, max_chars: int = 12000) -> str:
        cleaned = clean_extracted_text(text).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return f"{cleaned[:max_chars].rstrip()}..."

    @staticmethod
    def _validate_public_url(url: str):
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AppError("Provide a valid public http(s) article URL.", code="invalid_article_url", status_code=400)

        hostname = parsed.hostname or ""
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            raise AppError("Localhost URLs are not allowed for article import.", code="invalid_article_url", status_code=400)

        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError as exc:
            raise AppError("The article URL host could not be resolved.", code="invalid_article_url", status_code=400) from exc

        for info in infos:
            ip_text = info[4][0]
            try:
                ip_value = ipaddress.ip_address(ip_text)
            except ValueError:
                continue
            if ip_value.is_private or ip_value.is_loopback or ip_value.is_reserved or ip_value.is_link_local:
                raise AppError(
                    "Only public open-access article URLs are allowed.",
                    code="invalid_article_url",
                    status_code=400,
                )
        return parsed

    @staticmethod
    def _fetch_html(url: str) -> str:
        headers = {
            "User-Agent": "MedAgenticRAGAssistant/1.2 (educational project)",
        }
        try:
            response = httpx.get(url, headers=headers, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise AppError(
                    "The provided URL did not return an HTML article page.",
                    code="article_text_unavailable",
                    status_code=400,
                )
            return response.text
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Open-access article retrieval failed.") from exc

    @staticmethod
    def _extract_article_text(html_payload: str) -> tuple[str, str]:
        soup = BeautifulSoup(html_payload, "html.parser")
        for node in soup(["script", "style", "noscript", "svg", "canvas", "form", "button", "nav", "footer", "header"]):
            node.decompose()

        title = ""
        if soup.title:
            title = normalize_whitespace(soup.title.get_text(" ", strip=True))
        if not title:
            heading = soup.find(["h1", "h2"])
            if heading:
                title = normalize_whitespace(heading.get_text(" ", strip=True))

        paragraph_texts: list[str] = []
        seen: set[str] = set()
        for selector in HTML_PARAGRAPH_SELECTORS:
            for node in soup.select(selector):
                text = normalize_whitespace(node.get_text(" ", strip=True))
                if len(text) < 40 or text in seen:
                    continue
                seen.add(text)
                paragraph_texts.append(text)
            if len(paragraph_texts) >= 8:
                break

        if not paragraph_texts:
            for node in soup.find_all("p"):
                text = normalize_whitespace(node.get_text(" ", strip=True))
                if len(text) < 40 or text in seen:
                    continue
                seen.add(text)
                paragraph_texts.append(text)

        return title, clean_extracted_text("\n\n".join(paragraph_texts))

    @staticmethod
    def _extract_pmcid_from_url(url: str) -> str | None:
        match = re.search(r"/articles/(PMC\d+)/?", url, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).upper()
