from __future__ import annotations

from app.services.rag_service import RagService, RetrievedChunk
from app.utils.text import normalize_whitespace, strip_unsafe_guidance, to_excerpt


def test_normalize_whitespace_repairs_common_pdf_mojibake():
    broken = b"Addison\xe2\x80\x99s disease and calci\xef\xac\x81cation".decode("latin-1")

    assert normalize_whitespace(broken) == "Addison's disease and calcification"


def test_strip_unsafe_guidance_removes_treatment_and_dosing_sentences():
    text = (
        "Addison's disease is a rare adrenal disorder. "
        "Treatment involves hydrocortisone 15-25mg daily. "
        "Hyperpigmentation can be a sign."
    )

    result = strip_unsafe_guidance(text)

    assert "Addison's disease is a rare adrenal disorder." in result
    assert "Hyperpigmentation can be a sign." in result
    assert "15-25mg" not in result
    assert "Treatment involves" not in result


def test_to_excerpt_uses_safe_omission_note_for_treatment_only_text():
    text = "Treatment involves hydrocortisone 15-25mg daily and fludrocortisone 50mcg daily."

    assert to_excerpt(text) == "Source excerpt omitted because it contained treatment or dosing guidance."


def test_build_context_omits_unsafe_sentences_from_retrieved_chunks():
    chunk = RetrievedChunk(
        text=(
            "Addison's disease is a rare adrenal disorder. "
            "Treatment involves hydrocortisone 15-25mg daily."
        ),
        metadata={"filename": "notes.pdf", "page": 140},
        score=0.8,
    )

    context = RagService.build_context([chunk])

    assert "Addison's disease is a rare adrenal disorder." in context
    assert "15-25mg" not in context
    assert "Treatment involves" not in context
