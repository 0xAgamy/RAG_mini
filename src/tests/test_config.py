from __future__ import annotations

import pytest
from pydantic import ValidationError

from helpers.config import Settings


def test_settings_load_deterministic_test_environment():
    settings = Settings()

    assert settings.APP_NAME == "RAG-mini-test"
    assert settings.FILE_ALLOWED_TYPES == ["text/plain", "application/pdf"]
    assert settings.EMBEDING_MODEL_ID == "test-embedding-model"
    assert settings.EMBEDDING_MODEL_SIZE == 384
    assert settings.POSTGRES_MAIN_DATABASE == "rag_test"


def test_settings_report_missing_required_configuration(monkeypatch: pytest.MonkeyPatch):
    required = [
        "APP_NAME",
        "APP_VERSION",
        "FILE_ALLOWED_TYPES",
        "FILE_MAX_SIZE",
        "FILE_DEFAULT_CHUNK_SIZE",
        "GENERATION_BACKEND",
        "EMBEDDING_BACKEND",
        "VECTOR_DB_BACKEND",
        "VECTR_DB_PATH",
        "VECTOR_DB_DISTANCE_METHOD",
        "DEFAULT_LANGUAGE",
        "POSTGRES_USERNAME",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_MAIN_DATABASE",
        "STORAGE_PROVIDER",
        "MINIO_ENDPOINT",
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
        "MINIO_BUCKET_NAME",
        "MINIO_SECURE",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "CELERY_TASK_SERIALIZER",
        "CELERY_TASK_TIME_LIMIT",
        "CELERY_WORKER_CONCURRENCY",
    ]
    for name in required:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
