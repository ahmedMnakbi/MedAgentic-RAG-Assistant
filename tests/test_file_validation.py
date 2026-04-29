from __future__ import annotations

import pytest

from app.core.exceptions import FileValidationError, UnsupportedMediaTypeError
from app.utils.file_validation import (
    validate_content_type,
    validate_file_size,
    validate_pdf_extension,
    validate_pdf_signature,
)


def test_validate_pdf_extension_rejects_non_pdf():
    with pytest.raises(FileValidationError):
        validate_pdf_extension("notes.txt")


def test_validate_content_type_rejects_non_pdf():
    with pytest.raises(UnsupportedMediaTypeError):
        validate_content_type("text/plain")


def test_validate_content_type_allows_generic_octet_stream():
    validate_content_type("application/octet-stream")


def test_validate_file_size_rejects_empty():
    with pytest.raises(FileValidationError):
        validate_file_size(b"", max_bytes=10)


def test_validate_pdf_signature_rejects_invalid_signature():
    with pytest.raises(FileValidationError):
        validate_pdf_signature(b"not-a-pdf")
