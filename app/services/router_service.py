from __future__ import annotations

import re

from app.core.constants import DEFAULT_ROUTER_MODE, ROUTER_KEYWORDS

URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
DOCUMENT_REFERENCE_TERMS = (
    "uploaded",
    "upload",
    "pdf",
    "document",
    "file",
    "notes",
    "according to the document",
    "from this pdf",
    "from the pdf",
    "from my file",
    "from the uploaded",
)
FULL_TEXT_LITERATURE_TERMS = (
    "full text",
    "full-text",
    "open literature",
    "open access",
    "real articles",
    "not just abstracts",
    "systematic search",
    "literature",
    "articles",
    "papers",
    "studies",
)
PUBMED_TERMS = ("pubmed", "pmid", "ncbi")


class RouterService:
    def resolve_mode(
        self,
        requested_mode: str,
        question: str,
        *,
        document_ids: list[str] | None = None,
    ) -> str:
        if requested_mode != "auto":
            if requested_mode == "document_rag":
                return "rag"
            if requested_mode == "pubmed_metadata":
                return "pubmed"
            return requested_mode

        lowered = question.lower()
        if URL_PATTERN.search(question):
            return "open_article"
        if document_ids or self.references_uploaded_documents(lowered):
            for mode in ("summarize", "simplify", "quiz"):
                if any(keyword in lowered for keyword in ROUTER_KEYWORDS.get(mode, ())):
                    return mode
            return "document_rag"
        if any(term in lowered for term in PUBMED_TERMS):
            return "pubmed"
        if any(term in lowered for term in FULL_TEXT_LITERATURE_TERMS):
            return "open_literature"
        for mode, keywords in ROUTER_KEYWORDS.items():
            if mode == "pubmed":
                continue
            if mode == "prompt_enhance":
                if any(keyword in lowered for keyword in keywords):
                    return mode
                continue
            if any(keyword in lowered for keyword in keywords):
                return "general_education"
        return "general_education"

    @staticmethod
    def references_uploaded_documents(lowered_question: str) -> bool:
        return any(term in lowered_question for term in DOCUMENT_REFERENCE_TERMS)
