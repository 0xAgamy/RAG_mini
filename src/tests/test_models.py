from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.ProjectModel import ProjectModel
from models.db_schemes import Asset, DataChunk, Project, RetrievedDocument
from models.db_schemes.ragdb.schemes.ragdb_base import SQLAlchemyBase


def run(awaitable):
    return asyncio.run(awaitable)


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class FakeResult:
    def __init__(self, value=None, rows=None):
        self.value = value
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.value

    def scalar(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, results: list[FakeResult] | None = None):
        self.results = iter(results or [])
        self.added: list[Any] = []
        self.added_batches: list[list[Any]] = []
        self.commits = 0
        self.refreshed: list[Any] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def begin(self):
        return AsyncContext(self)

    async def execute(self, statement):
        return next(self.results)

    def add(self, record):
        self.added.append(record)

    def add_all(self, records):
        self.added_batches.append(list(records))

    async def commit(self):
        self.commits += 1

    async def refresh(self, record):
        self.refreshed.append(record)


def session_factory_for(session: FakeSession):
    return lambda: session


def test_model_factory_methods_keep_the_session_factory(test_settings):
    db_client = object()

    project_model = run(ProjectModel.create_instance(db_client=db_client))
    chunk_model = run(ChunkModel.create_instance(db_client=db_client))
    asset_model = run(AssetModel.create_instance(db_client=db_client))

    assert project_model.db_client is db_client
    assert chunk_model.db_client is db_client
    assert asset_model.db_client is db_client


def test_create_project_adds_commits_and_refreshes(test_settings):
    session = FakeSession()
    model = ProjectModel(session_factory_for(session))
    project = SimpleNamespace(project_id=1)

    result = run(model.create_project(project))

    assert result is project
    assert session.added == [project]
    assert session.commits == 1
    assert session.refreshed == [project]


def test_get_project_or_create_one_returns_existing_project(test_settings):
    existing = SimpleNamespace(project_id=8)
    session = FakeSession([FakeResult(value=existing)])
    model = ProjectModel(session_factory_for(session))

    result = run(model.get_project_or_create_one(project_id=8))

    assert result is existing
    assert session.added == []


def test_get_project_or_create_one_creates_missing_project(test_settings):
    session = FakeSession([FakeResult(value=None)])
    model = ProjectModel(session_factory_for(session))

    result = run(model.get_project_or_create_one(project_id=8))

    assert isinstance(result, Project)
    assert result.project_id == 8
    assert session.added == [result]
    assert session.commits == 1
    assert session.refreshed == [result]


def test_chunk_model_batches_records_and_returns_count(test_settings):
    session = FakeSession()
    model = ChunkModel(session_factory_for(session))
    chunks = [object() for _ in range(5)]

    result = run(model.insert_many_chunks(chunks, batch_size=2))

    assert result == 5
    assert [len(batch) for batch in session.added_batches] == [2, 2, 1]
    assert session.commits == 1


def test_chunk_model_returns_total_count(test_settings):
    session = FakeSession([FakeResult(value=17)])
    model = ChunkModel(session_factory_for(session))

    result = run(model.get_total_chunks_count(project_id=3))

    assert result == 17


def test_asset_model_creates_and_lists_assets(test_settings):
    expected_assets = [object(), object()]
    session = FakeSession([FakeResult(rows=expected_assets)])
    model = AssetModel(session_factory_for(session))
    asset = SimpleNamespace(asset_id=1)

    created = run(model.create_asset(asset))
    listed = run(
        model.get_all_projects_assets(
            asset_project_id=3,
            asset_type="file",
        )
    )

    assert created is asset
    assert listed == expected_assets
    assert session.added == [asset]


def test_retrieved_document_serializes_text_and_score():
    document = RetrievedDocument(text="retrieved", score=0.75)

    assert document.model_dump() == {"text": "retrieved", "score": 0.75}


def test_database_metadata_contains_rag_tables():
    assert {"projects", "assets", "chunks"}.issubset(
        SQLAlchemyBase.metadata.tables
    )
    assert Project.__table__.c.project_id.primary_key is True
    assert Asset.__table__.c.asset_project_id.foreign_keys
    assert DataChunk.__table__.c.chunk_project_id.foreign_keys
    assert DataChunk.__table__.c.chunkd_order is not None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "AssetModel.get_asset_record currently calls session.execute without "
        "awaiting it; keep this regression visible until the model is fixed."
    )
)
def test_asset_lookup_awaits_execute(test_settings):
    class BrokenLookupSession(FakeSession):
        def execute(self, statement):
            # This synchronous result makes the missing await fail immediately
            # without leaving an un-awaited coroutine behind.
            return object()

    session = BrokenLookupSession()
    model = AssetModel(session_factory_for(session))

    result = run(
        model.get_asset_record(
            asset_project_id=3,
            asset_name="document.txt",
        )
    )

    assert result.asset_id == 1
