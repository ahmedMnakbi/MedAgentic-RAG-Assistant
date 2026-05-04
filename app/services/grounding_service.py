from __future__ import annotations

import re

from app.schemas.rag import GroundingResult
from app.services.rag_service import RetrievedChunk
from app.utils.text import keyword_overlap


class GroundingService:
    def check(self, answer: str, chunks: list[RetrievedChunk]) -> GroundingResult:
        if not chunks:
            return GroundingResult(
                grounded=False,
                unsupported_claims=["No source chunks were available."],
                warning="The answer has no retrievable source context.",
            )

        source_text = " ".join(chunk.text for chunk in chunks)
        sentences = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+", answer or "")
            if len(item.strip()) > 40
        ]
        if not sentences:
            return GroundingResult(grounded=True, citation_coverage=1.0)

        unsupported = [
            sentence
            for sentence in sentences
            if keyword_overlap(sentence, source_text) == 0 and "[" not in sentence
        ]
        coverage = (len(sentences) - len(unsupported)) / max(1, len(sentences))
        return GroundingResult(
            grounded=coverage >= 0.5,
            unsupported_claims=unsupported[:5],
            citation_coverage=coverage,
            warning=None if coverage >= 0.5 else "Some answer claims were not clearly supported by retrieved context.",
        )
