from __future__ import annotations

from pathlib import Path
from typing import Any


class PDFLoaderClient:
    def load_pages(self, file_path: Path) -> list[Any]:
        try:
            from langchain_community.document_loaders import PyPDFLoader

            loader = PyPDFLoader(str(file_path), mode="page")
            pages = loader.load()
            if self._readable_text_length(pages) >= 80:
                return pages
        except Exception:
            pages = []

        fallback_pages = self._load_with_pypdf(file_path)
        if fallback_pages:
            return fallback_pages
        return pages

    @staticmethod
    def _readable_text_length(pages: list[Any]) -> int:
        return sum(len(str(getattr(page, "page_content", "") or "").strip()) for page in pages)

    @staticmethod
    def _load_with_pypdf(file_path: Path) -> list[Any]:
        from langchain_core.documents import Document
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(Document(page_content=text, metadata={"page": index, "source": str(file_path)}))
        return pages
