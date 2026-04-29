from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        app_env="test",
        app_debug=False,
        upload_dir=tmp_path / "uploads",
        chroma_persist_directory=tmp_path / "chroma",
        documents_registry_file=tmp_path / "documents.json",
        groq_api_key="test-key",
        groq_model="test-model",
        ncbi_email="student@example.com",
        max_upload_size_mb=1,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
