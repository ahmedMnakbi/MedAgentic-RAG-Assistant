from __future__ import annotations

from pydantic import BaseModel, Field


class PubMedArticle(BaseModel):
    pmid: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str
    publication_date: str
    pubmed_url: str
