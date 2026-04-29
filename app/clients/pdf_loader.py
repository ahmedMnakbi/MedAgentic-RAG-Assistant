from __future__ import annotations

from pathlib import Path
from typing import Any


class PDFLoaderClient:
    def load_pages(self, file_path: Path) -> list[Any]:
        from langchain_community.document_loaders import PyPDFLoader

        loader = PyPDFLoader(str(file_path), mode="page")
        return loader.load()
