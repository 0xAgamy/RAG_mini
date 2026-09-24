from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import main as main_module


def run(awaitable):
    return asyncio.run(awaitable)


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class FakeVectorClient:
    def __init__(self):
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.disconnected = True


def test_startup_and_shutdown_configure_application_clients(
    monkeypatch: pytest.MonkeyPatch,
):
    settings = SimpleNamespace(
        POSTGRES_USERNAME="user",
        POSTGRES_PASSWORD="password",
        POSTGRES_HOST="db",
        POSTGRES_PORT="5432",
        POSTGRES_MAIN_DATABASE="rag",
        STORAGE_PROVIDER="minio",
        GENERATION_BACKEND="OPENAI",
        GENERATION_MODEL_ID="generation-model",
        EMBEDDING_BACKEND="COHERE",
        EMBEDING_MODEL_ID="embedding-model",
        EMBEDDING_MODEL_SIZE=384,
        VECTOR_DB_BACKEND="QDRANT",
        DEFAULT_LANGUAGE="en",
    )
    app = SimpleNamespace()
    engine = FakeEngine()
    vector_client = FakeVectorClient()
    storage_client = object()
    generation_client = SimpleNamespace()
    embedding_client = SimpleNamespace()
    calls = SimpleNamespace(
        storage_init=[],
        llm_init=[],
        vector_init=[],
        generation_models=[],
        embedding_models=[],
        parser_languages=[],
        engine_urls=[],
    )

    generation_client.set_generation_model = lambda model_id: calls.generation_models.append(
        model_id
    )
    embedding_client.set_embedding_model = lambda model_id, embedding_size: calls.embedding_models.append(
        (model_id, embedding_size)
    )

    def create_engine(url):
        calls.engine_urls.append(url)
        return engine

    def make_session_factory(db_engine, **kwargs):
        return SimpleNamespace(db_engine=db_engine, kwargs=kwargs)

    class FakeStorageFactory:
        def __init__(self, config):
            calls.storage_init.append(config)

        def create(self):
            return storage_client

    class FakeLLMFactory:
        def __init__(self, config):
            calls.llm_init.append(config)

        def create(self, provider):
            return generation_client if provider == "OPENAI" else embedding_client

    class FakeVectorFactory:
        def __init__(self, config, db_client):
            calls.vector_init.append((config, db_client))

        def create(self, provider):
            return vector_client

    class FakeTemplateParser:
        def __init__(self, language):
            calls.parser_languages.append(language)

    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(main_module, "create_async_engine", create_engine)
    monkeypatch.setattr(main_module, "sessionmaker", make_session_factory)
    monkeypatch.setattr(main_module, "StorageFactory", FakeStorageFactory)
    monkeypatch.setattr(main_module, "LLMProviderFactory", FakeLLMFactory)
    monkeypatch.setattr(
        main_module,
        "VectorDBProviderFactory",
        FakeVectorFactory,
    )
    monkeypatch.setattr(main_module, "TemplateParser", FakeTemplateParser)

    run(main_module.startup_span(app))
    assert app.db_engine is engine
    assert app.db_client.db_engine is engine
    assert app.db_client.kwargs["class_"] is main_module.AsyncSession
    assert app.db_client.kwargs["expire_on_commit"] is False
    assert app.storage_client is storage_client
    assert app.generation_client is generation_client
    assert app.embedding_client is embedding_client
    assert app.vectordb_client is vector_client
    assert vector_client.connected is True
    assert calls.engine_urls == [
        "postgresql+asyncpg://user:password@db:5432/rag"
    ]
    assert calls.generation_models == ["generation-model"]
    assert calls.embedding_models == [("embedding-model", 384)]
    assert calls.parser_languages == ["en"]

    run(main_module.shutdown_span(app))
    assert engine.disposed is True
    assert vector_client.disconnected is True
