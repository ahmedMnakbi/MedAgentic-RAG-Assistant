from __future__ import annotations

from app.core.constants import ALLOWED_PDF_CONTENT_TYPES
from app.core.exceptions import FileValidationError, UnsupportedMediaTypeError


def validate_pdf_upload(
    *,
    filename: str,
    content_type: str | None,
    content: bytes,
    max_bytes: int,
) -> None:
    validate_pdf_extension(filename)
    validate_content_type(content_type)
    validate_file_size(content, max_bytes=max_bytes)
    validate_pdf_signature(content)


def validate_pdf_extension(filename: str) -> None:
    if not filename.lower().endswith(".pdf"):
        raise FileValidationError("Only PDF uploads are supported in v1.")


def validate_content_type(content_type: str | None) -> None:
    if content_type and content_type not in ALLOWED_PDF_CONTENT_TYPES:
        raise UnsupportedMediaTypeError("The uploaded file must use a PDF content type.")


def validate_file_size(content: bytes, *, max_bytes: int) -> None:
    if len(content) == 0:
        raise FileValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise FileValidationError(f"The uploaded file exceeds the maximum size of {max_bytes} bytes.")


def validate_pdf_signature(content: bytes) -> None:
    if not content.startswith(b"%PDF"):
        raise FileValidationError("The uploaded file does not look like a valid PDF.")
