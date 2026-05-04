from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.clients.ncbi_client import NCBIClient
from app.core.config import Settings
from app.core.constants import PMC_URL_TEMPLATE
from app.core.exceptions import AppError, ExternalServiceError
from app.schemas.open_article import ArticleSection, OpenArticleSource
from app.utils.text import clean_extracted_text, normalize_whitespace, strip_unsafe_guidance

ARTICLE_SELECTORS = (
    "article",
    "main article",
    "main",
    "[role='main']",
    ".article",
    ".article__body",
    ".article-body",
    ".content",
    ".main-content",
)


class OpenArticleService:
    def __init__(self, *, settings: Settings, ncbi_client: NCBIClient) -> None:
        self.settings = settings
        self.ncbi_client = ncbi_client

    def import_url(self, url: str) -> OpenArticleSource:
        parsed = self.validate_public_url(url)
        if self._is_cureus_url(parsed.geturl()) and not self.settings.open_literature_enable_cureus_experimental:
            return OpenArticleSource(
                title=parsed.geturl(),
                url=parsed.geturl(),
                source_type="cureus_link_only",
                source_name="Cureus",
                source_url=parsed.geturl(),
                full_text_status="restricted",
                allowed_for_ai_processing=False,
                warnings=[
                    "Cureus URLs are treated as link-only by default because terms/licensing are not enabled for automatic AI ingestion.",
                    "If the article has a PMC Open Access version, import the PMC URL instead.",
                ],
            )

        pmcid = self.extract_pmcid(parsed.geturl())
        if pmcid:
            return self._import_pmc(pmcid, parsed.geturl())

        html_payload = self._fetch_html(parsed.geturl())
        article = self._extract_html_article(html_payload, parsed.geturl())
        if article.full_text_status != "full_text":
            raise AppError(
                "The article URL did not expose enough readable open-access text to use for study generation.",
                code="article_text_unavailable",
                status_code=400,
            )
        return article

    def build_context(self, article: OpenArticleSource, *, max_chars: int | None = None) -> str:
        usable_text = strip_unsafe_guidance(article.body_text)
        if max_chars:
            usable_text = usable_text[:max_chars].rstrip()
        label = article.title
        if article.pmid:
            label += f" | PMID {article.pmid}"
        if article.pmcid:
            label += f" | {article.pmcid}"
        label += f" | Source: {article.full_text_status}"
        return f"[Open Article Source: {label}]\n{usable_text}" if usable_text else ""

    def _import_pmc(self, pmcid: str, url: str) -> OpenArticleSource:
        full_text = clean_extracted_text(self.ncbi_client.fetch_pmc_full_text(pmcid)).strip()
        if len(full_text) < 250:
            raise AppError(
                "The PMC article did not expose enough readable full text to use for study generation.",
                code="article_text_unavailable",
                status_code=400,
            )
        sections = [ArticleSection(title="PMC full text", text=full_text)]
        return OpenArticleSource(
            title=f"PMC article {pmcid}",
            url=url,
            source_type="pmc_xml",
            source_name="PubMed Central",
            source_url=PMC_URL_TEMPLATE.format(pmcid=pmcid),
            pmcid=pmcid,
            body_text=full_text,
            sections=sections,
            extraction_quality_score=0.95,
            full_text_status="full_text",
            allowed_for_ai_processing=True,
            warnings=["PMC full text was retrieved through the NCBI/PMC path."],
        )

    def _extract_html_article(self, html_payload: str, url: str) -> OpenArticleSource:
        soup = BeautifulSoup(html_payload, "html.parser")
        for node in soup(["script", "style", "noscript", "svg", "canvas", "form", "button", "nav", "footer", "header", "aside"]):
            node.decompose()

        title = self._meta_content(soup, "citation_title") or self._meta_content(soup, "og:title")
        if not title and soup.title:
            title = normalize_whitespace(soup.title.get_text(" ", strip=True))
        if not title:
            heading = soup.find(["h1", "h2"])
            title = normalize_whitespace(heading.get_text(" ", strip=True)) if heading else url

        authors = [
            normalize_whitespace(node.get("content", ""))
            for node in soup.select("meta[name='citation_author']")
            if normalize_whitespace(node.get("content", ""))
        ]
        doi = self._meta_content(soup, "citation_doi")
        journal = self._meta_content(soup, "citation_journal_title")
        publication_date = self._meta_content(soup, "citation_publication_date")
        license_text = self._meta_content(soup, "citation_license") or self._meta_content(soup, "dc.rights")
        abstract = self._meta_content(soup, "citation_abstract")

        root = self._best_article_root(soup)
        sections = self._extract_sections(root)
        body_text = clean_extracted_text("\n\n".join(section.text for section in sections)).strip()
        quality = self._quality_score(body_text, sections)
        warnings = []
        allowed = self._license_allows_ai(license_text, url)
        if not license_text:
            warnings.append("No clear machine-readable open-access license was found; use with caution.")
        if quality < 0.35:
            warnings.append("Readable article extraction appears partial or low quality.")
        if len(body_text) < 250:
            return OpenArticleSource(
                title=title,
                url=url,
                source_type="generic_html",
                source_name=urlparse(url).netloc,
                doi=doi,
                authors=authors,
                publication_date=publication_date,
                journal=journal,
                license=license_text,
                abstract=abstract,
                body_text=body_text,
                sections=sections,
                extraction_quality_score=quality,
                warnings=warnings + ["Too little readable article text was extracted."],
                full_text_status="extraction_failed",
                allowed_for_ai_processing=False,
            )
        return OpenArticleSource(
            title=title,
            url=url,
            source_type="generic_html",
            source_name=urlparse(url).netloc,
            source_url=url,
            doi=doi,
            authors=authors,
            publication_date=publication_date,
            journal=journal,
            license=license_text,
            abstract=abstract,
            body_text=body_text,
            sections=sections,
            extraction_quality_score=quality,
            warnings=warnings,
            full_text_status="full_text",
            allowed_for_ai_processing=allowed,
        )

    @staticmethod
    def validate_public_url(url: str):
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
    def extract_pmcid(url: str) -> str | None:
        match = re.search(r"/articles/(PMC\d+)/?", url, flags=re.IGNORECASE)
        return match.group(1).upper() if match else None

    @staticmethod
    def _fetch_html(url: str) -> str:
        headers = {"User-Agent": "MARA/2.0 (educational open article import)"}
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
    def _best_article_root(soup: BeautifulSoup):
        for selector in ARTICLE_SELECTORS:
            node = soup.select_one(selector)
            if node and len(node.get_text(" ", strip=True)) > 500:
                return node
        return soup

    @staticmethod
    def _extract_sections(root) -> list[ArticleSection]:
        sections: list[ArticleSection] = []
        current_title = "Article text"
        current_parts: list[str] = []

        for node in root.find_all(["h1", "h2", "h3", "p", "li"], recursive=True):
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if len(text) < 25 and node.name not in {"h1", "h2", "h3"}:
                continue
            if node.name in {"h1", "h2", "h3"}:
                if current_parts:
                    sections.append(ArticleSection(title=current_title, text="\n\n".join(current_parts)))
                    current_parts = []
                current_title = text[:120] or "Section"
                continue
            if text:
                current_parts.append(text)
        if current_parts:
            sections.append(ArticleSection(title=current_title, text="\n\n".join(current_parts)))
        if not sections:
            paragraphs = [
                normalize_whitespace(node.get_text(" ", strip=True))
                for node in root.find_all("p")
                if len(normalize_whitespace(node.get_text(" ", strip=True))) >= 40
            ]
            if paragraphs:
                sections.append(ArticleSection(title="Article text", text="\n\n".join(paragraphs)))
        return sections

    @staticmethod
    def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
        node = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        value = normalize_whitespace(node.get("content", "")) if node else ""
        return value or None

    @staticmethod
    def _quality_score(body_text: str, sections: list[ArticleSection]) -> float:
        length_score = min(len(body_text) / 5000, 1.0)
        section_score = min(len(sections) / 5, 1.0)
        return round((length_score * 0.7) + (section_score * 0.3), 3)

    @staticmethod
    def _license_allows_ai(license_text: str | None, url: str) -> bool:
        lowered = (license_text or "").lower()
        if not lowered:
            return True
        if "creativecommons" in lowered or "cc-by" in lowered or "cc by" in lowered:
            return True
        if "pmc.ncbi.nlm.nih.gov" in urlparse(url).netloc:
            return True
        return False

    @staticmethod
    def _is_cureus_url(url: str) -> bool:
        return "cureus.com" in (urlparse(url).hostname or "").lower()
