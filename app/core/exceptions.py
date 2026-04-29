from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "app_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class FileValidationError(AppError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=400, code="file_validation_error", details=details)


class UnsupportedMediaTypeError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=415, code="unsupported_media_type")


class InvalidPdfError(AppError):
    def __init__(self, message: str = "The uploaded PDF could not be parsed.") -> None:
        super().__init__(message, status_code=400, code="invalid_pdf")


class EmptyPdfError(AppError):
    def __init__(self, message: str = "The uploaded PDF does not contain extractable text.") -> None:
        super().__init__(message, status_code=400, code="empty_pdf")


class NotConfiguredError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503, code="not_configured")


class ExternalServiceError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502, code="external_service_error")


class ResourceNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404, code="resource_not_found")
