from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.storage.StorageProviderFactory import StorageFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory


llm_factory_module = importlib.import_module(
    "stores.llm.LLMProviderFactory"
)
storage_factory_module = importlib.import_module(
    "stores.storage.StorageProviderFactory"
)
vector_factory_module = importlib.import_module(
    "stores.vectordb.VectorDBProviderFactory"
)


def llm_config():
    return SimpleNamespace(
        OPENAI_API_KEY="openai-key",
        OPENAI_API_URL="https://example.invalid/v1",
        COHERE_API_KEY="cohere-key",
        DEFAULT_GENERATION_MAX_OUTPUT_TOKENS=256,
        DEFAULT_GENERATION_TEMPERATURE=0.2,
        DEFAULT_INPUT_MAX_CHARACTERS=2048,
    )


def vector_config():
    return SimpleNamespace(
        VECTR_DB_PATH="localhost:6333",
        EMBEDDING_MODEL_SIZE=1536,
        VECTOR_DB_DISTANCE_METHOD="COSINE",
        VECTOR_DB_PGVEC_INDEX_THRESHOLD=100,
    )


def test_llm_factory_creates_openai_provider_with_config(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    class FakeOpenAIProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_factory_module, "OpenAIProvider", FakeOpenAIProvider)

    result = LLMProviderFactory(llm_config()).create("OPENAI")

    assert isinstance(result, FakeOpenAIProvider)
    assert captured["api_key"] == "openai-key"
    assert captured["base_url"] == "https://example.invalid/v1"
    assert captured["default_input_max_characters"] == 2048


def test_llm_factory_creates_cohere_provider(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeCohereProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_factory_module, "CoHereProvider", FakeCohereProvider)

    result = LLMProviderFactory(llm_config()).create("COHERE")

    assert isinstance(result, FakeCohereProvider)
    assert captured["api_key"] == "cohere-key"


def test_llm_factory_returns_none_for_unknown_provider():
    assert LLMProviderFactory(llm_config()).create("UNKNOWN") is None


def test_vector_factory_creates_qdrant_provider(
    test_settings: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    class FakeQdrantProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        vector_factory_module, "QdrantDBProvider", FakeQdrantProvider
    )

    result = VectorDBProviderFactory(
        config=vector_config(),
        db_client=object(),
    ).create("QDRANT")

    assert isinstance(result, FakeQdrantProvider)
    assert captured == {
        "db_client": "localhost:6333",
        "default_vector_size": 1536,
        "distance_method": "COSINE",
    }


def test_vector_factory_creates_pgvector_provider(
    test_settings: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}
    db_client = object()

    class FakePgVectorProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        vector_factory_module, "PgVectorProvider", FakePgVectorProvider
    )

    result = VectorDBProviderFactory(
        config=vector_config(),
        db_client=db_client,
    ).create("PGVECTOR")

    assert isinstance(result, FakePgVectorProvider)
    assert captured["db_client"] is db_client
    assert captured["default_vector_size"] == 1536
    assert captured["index_threshold"] == 100


def test_vector_factory_returns_none_for_unknown_provider(test_settings: SimpleNamespace):
    assert (
        VectorDBProviderFactory(
            config=vector_config(),
            db_client=object(),
        ).create("UNKNOWN")
        is None
    )


def test_storage_factory_supports_minio_and_s3_names(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = []

    class FakeMinioStorage:
        def __init__(self, config):
            calls.append(config)

    monkeypatch.setattr(storage_factory_module, "MinIoStorage", FakeMinioStorage)
    config = SimpleNamespace(STORAGE_PROVIDER="S3")

    result = StorageFactory(config).create()

    assert isinstance(result, FakeMinioStorage)
    assert calls == [config]


def test_storage_factory_rejects_unknown_provider():
    config = SimpleNamespace(STORAGE_PROVIDER="filesystem")

    with pytest.raises(ValueError, match="Unsupported storage provider"):
        StorageFactory(config).create()
