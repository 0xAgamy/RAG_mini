"""Shared test configuration.

The application is written with ``src`` as its import root (for example,
``from controllers import NLPController``).  Keeping that path setup here means
the same tests work whether pytest is started from the repository root or from
``src``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Awaitable, TypeVar

import pytest


SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


# Settings are loaded at import time by celery_app.  Use deterministic,
# non-production values so importing a task never requires a real service or
# reads a developer's local .env file.
TEST_ENV = {
    "APP_NAME": "RAG-mini-test",
    "APP_VERSION": "test",
    "FILE_ALLOWED_TYPES": '["text/plain", "application/pdf"]',
    "FILE_MAX_SIZE": "10",
    "FILE_DEFAULT_CHUNK_SIZE": "512",
    "GENERATION_BACKEND": "OPENAI",
    "EMBEDDING_BACKEND": "COHERE",
    "GENERATION_MODEL_ID": "test-generation-model",
    # Keep the legacy spelling used by helpers.config.Settings.
    "EMBEDING_MODEL_ID": "test-embedding-model",
    "EMBEDDING_MODEL_SIZE": "384",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_API_URL": "https://test.invalid/v1",
    "COHERE_API_KEY": "test-cohere-key",
    "DEFAULT_INPUT_MAX_CHARACTERS": "1024",
    "DEFAULT_GENERATION_MAX_OUTPUT_TOKENS": "200",
    "DEFAULT_GENERATION_TEMPERATURE": "0.1",
    "VECTOR_DB_BACKEND_LITERAL": '["QDRANT", "PGVECTOR"]',
    "VECTOR_DB_BACKEND": "QDRANT",
    "VECTR_DB_PATH": "test-vector-db",
    "VECTOR_DB_DISTANCE_METHOD": "COSINE",
    "VECTOR_DB_PGVEC_INDEX_THRESHOLD": "100",
    "DEFAULT_LANGUAGE": "en",
    "POSTGRES_USERNAME": "test-user",
    "POSTGRES_PASSWORD": "test-password",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_MAIN_DATABASE": "rag_test",
    "STORAGE_PROVIDER": "minio",
    "MINIO_ENDPOINT": "localhost:9000",
    "MINIO_ROOT_USER": "test-user",
    "MINIO_ROOT_PASSWORD": "test-password",
    "MINIO_BUCKET_NAME": "rag-test",
    "MINIO_SECURE": "false",
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
    "CELERY_TASK_SERIALIZER": "json",
    "CELERY_TASK_TIME_LIMIT": "600",
    "CELERY_TASK_ACKS_LATE": "true",
    "CELERY_WORKER_CONCURRENCY": "1",
}
os.environ.update(TEST_ENV)


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Return a lightweight settings object and isolate controller settings."""

    settings = SimpleNamespace(
        APP_NAME="RAG-mini-test",
        APP_VERSION="test",
        FILE_ALLOWED_TYPES=["text/plain", "application/pdf"],
        FILE_MAX_SIZE=10,
        FILE_DEFAULT_CHUNK_SIZE=512,
    )
    import importlib

    base_controller_module = importlib.import_module("controllers.BaseController")
    monkeypatch.setattr(
        base_controller_module,
        "get_settings",
        lambda: settings,
    )
    return settings


@pytest.fixture
def isolated_project_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Keep controller path tests out of the checked-in assets directory."""

    from controllers.ProjectController import ProjectController

    project_path = tmp_path / "project"
    project_path.mkdir(parents=True, exist_ok=True)

    def get_project_path(self, project_id: int) -> str:
        project_path.mkdir(parents=True, exist_ok=True)
        return str(project_path)

    monkeypatch.setattr(ProjectController, "get_project_path", get_project_path)
    return project_path


T = TypeVar("T")


def run_async(awaitable: Awaitable[T]) -> T:
    """Run an awaitable from a synchronous pytest test.

    The project does not currently require ``pytest-asyncio`` just to execute
    these unit tests, so the helper keeps the test dependency small while still
    exercising the real async methods.
    """

    return asyncio.run(awaitable)  # type: ignore[arg-type]
