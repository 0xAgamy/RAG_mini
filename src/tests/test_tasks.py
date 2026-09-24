from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from tasks import data_indexing, file_processing


def run(awaitable):
    return asyncio.run(awaitable)


class FakeTaskInstance:
    def __init__(self):
        self.states: list[dict[str, Any]] = []

    def update_state(self, **kwargs):
        self.states.append(kwargs)


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


class FakeVectorDB:
    def __init__(self):
        self.disconnected = False
        self.created: list[dict[str, Any]] = []

    async def create_collection(self, **kwargs):
        self.created.append(kwargs)
        return True

    async def disconnect(self):
        self.disconnected = True


class FakeStorage:
    def __init__(self):
        self.reads: list[str] = []

    async def get_file_content(self, object_name: str):
        self.reads.append(object_name)
        return b"first line\nsecond line"


class FakeProject:
    project_id = 7


class FakeAssetRecord:
    asset_id = 11
    asset_name = "asset-document.txt"


class FakeDataChunk:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def install_file_processing_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    asset_record: object | None,
    state: dict[str, Any],
):
    engine = FakeEngine()
    vector_db = FakeVectorDB()
    storage = FakeStorage()

    async def get_setup_utils():
        return (
            engine,
            object(),
            object(),
            object(),
            object(),
            object(),
            object(),
            vector_db,
            object(),
            storage,
        )

    class FakeProjectModel:
        @classmethod
        async def create_instance(cls, db_client):
            return cls()

        async def get_project_or_create_one(self, project_id):
            return FakeProject()

    class FakeAssetModel:
        @classmethod
        async def create_instance(cls, db_client):
            return cls()

        async def get_asset_record(self, asset_project_id, asset_name):
            state["asset_lookup"] = (asset_project_id, asset_name)
            return asset_record

    class FakeChunkModel:
        @classmethod
        async def create_instance(cls, db_client):
            return cls()

        async def insert_many_chunks(self, chunks, batch_size=100):
            state["inserted_chunks"] = chunks
            return len(chunks)

    class FakeNLPController:
        def __init__(self, **kwargs):
            state["nlp_kwargs"] = kwargs

    class FakeProcessController:
        def __init__(self, project_id):
            state["processed_project_id"] = project_id

        def get_file_loader(self, content, source):
            return [SimpleNamespace(page_content=content.decode(), metadata={})]

        def process_file_content(self, file_content, chunk_size, overlap_size):
            return [SimpleNamespace(page_content="chunk", metadata={"source": "fake"})]

    monkeypatch.setattr(file_processing, "get_setup_utils", get_setup_utils)
    monkeypatch.setattr(file_processing, "ProjectModel", FakeProjectModel)
    monkeypatch.setattr(file_processing, "AssetModel", FakeAssetModel)
    monkeypatch.setattr(file_processing, "ChunkModel", FakeChunkModel)
    monkeypatch.setattr(file_processing, "NLPController", FakeNLPController)
    monkeypatch.setattr(file_processing, "ProcessController", FakeProcessController)
    monkeypatch.setattr(file_processing, "DataChunk", FakeDataChunk)

    return engine, vector_db, storage


def test_process_project_file_successfully_indexes_stored_content(
    monkeypatch: pytest.MonkeyPatch,
):
    state: dict[str, Any] = {}
    engine, vector_db, storage = install_file_processing_fakes(
        monkeypatch,
        asset_record=FakeAssetRecord(),
        state=state,
    )
    task = FakeTaskInstance()

    result = run(
        file_processing._process_project_file(
            task,
            project_id=7,
            file_id="asset-document.txt",
            chunk_size=100,
            overlap_size=20,
            do_reset=0,
        )
    )

    # The task currently exposes the legacy ``singal`` key; the test keeps the
    # characterization explicit so it can be updated with the public contract.
    assert result == {
        "singal": "processing_success",
        "inserted_chunks": 1,
        "processed_files": 1,
    }
    assert state["asset_lookup"] == (7, "asset-document.txt")
    assert state["processed_project_id"] == 7
    assert state["inserted_chunks"][0].chunk_text == "chunk"
    assert state["inserted_chunks"][0].chunk_project_id == 7
    assert task.states[-1]["status"] == "SUCCESS"
    assert storage.reads == ["asset-document.txt"]
    assert engine.disposed is True
    assert vector_db.disconnected is True


def test_process_project_file_reports_missing_asset_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
):
    state: dict[str, Any] = {}
    engine, vector_db, _ = install_file_processing_fakes(
        monkeypatch,
        asset_record=None,
        state=state,
    )
    task = FakeTaskInstance()

    with pytest.raises(Exception, match="No assets for file"):
        run(
            file_processing._process_project_file(
                task,
                project_id=7,
                file_id="missing.txt",
                chunk_size=100,
                overlap_size=20,
                do_reset=0,
            )
        )

    assert task.states[0]["state"] == "FAILURE"
    assert task.states[0]["meta"]["signal"] == "no_file_found_with_this_id"
    assert engine.disposed is True
    assert vector_db.disconnected is True


def install_indexing_fakes(
    monkeypatch: pytest.MonkeyPatch,
    state: dict[str, Any],
):
    engine = FakeEngine()
    vector_db = FakeVectorDB()
    pages = {
        1: [SimpleNamespace(chunk_id=101), SimpleNamespace(chunk_id=102)],
        2: [],
    }

    async def get_setup_utils():
        return (
            engine,
            object(),
            object(),
            object(),
            object(),
            object(),
            SimpleNamespace(embedding_size=384),
            vector_db,
            object(),
            object(),
        )

    class FakeProjectModel:
        @classmethod
        async def create_instance(cls, db_client):
            return cls()

        async def get_project_or_create_one(self, project_id):
            return FakeProject()

    class FakeChunkModel:
        @classmethod
        async def create_instance(cls, db_client):
            return cls()

        async def get_total_chunks_count(self, project_id):
            return 2

        async def get_project_chunks(self, project_id, page_no, page_size=50):
            state["page_requests"].append((project_id, page_no, page_size))
            return pages.get(page_no, [])

    class FakeNLPController:
        def __init__(self, **kwargs):
            self.embedding_size = 384

        def create_collection_name(self, project_id):
            return f"collection_384_{project_id}"

        async def index_into_vector_db(self, project, chunks, chunks_ids, do_reset=False):
            state["index_calls"].append(
                {
                    "project": project,
                    "chunks": chunks,
                    "chunks_ids": chunks_ids,
                    "do_reset": do_reset,
                }
            )
            return True

    class FakeProgress:
        def __init__(self, **kwargs):
            state["progress_created"] = kwargs

        def update(self, amount):
            state["progress_updates"].append(amount)

    state["page_requests"] = []
    state["index_calls"] = []
    state["progress_updates"] = []

    monkeypatch.setattr(data_indexing, "get_setup_utils", get_setup_utils)
    monkeypatch.setattr(data_indexing, "ProjectModel", FakeProjectModel)
    monkeypatch.setattr(data_indexing, "ChunkModel", FakeChunkModel)
    monkeypatch.setattr(data_indexing, "NLPController", FakeNLPController)
    monkeypatch.setattr(data_indexing, "tqdm", FakeProgress)

    return engine, vector_db


def test_index_data_content_processes_each_chunk_page(
    monkeypatch: pytest.MonkeyPatch,
):
    state: dict[str, Any] = {}
    engine, vector_db = install_indexing_fakes(monkeypatch, state)
    task = FakeTaskInstance()

    result = run(
        data_indexing._index_data_content(
            task,
            project_id=7,
            do_reset=1,
        )
    )

    assert result == {
        "signal": "insert_into_vector_db_success",
        "inserted_item_count": 2,
    }
    assert vector_db.created == [
        {
            "collection_name": "collection_384_7",
            "embedding_size": 384,
            "do_reset": 1,
        }
    ]
    assert state["page_requests"] == [(7, 1, 50), (7, 2, 50)]
    assert state["index_calls"][0]["chunks_ids"] == [101, 102]
    assert state["progress_updates"] == [2]
    assert task.states[-1]["state"] == "SUCCESS"
    assert engine.disposed is True
    assert vector_db.disconnected is True


def test_index_data_content_marks_insertion_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    state: dict[str, Any] = {}
    engine, vector_db = install_indexing_fakes(monkeypatch, state)
    original_controller = data_indexing.NLPController

    class FailingController(original_controller):
        async def index_into_vector_db(self, **kwargs):
            return False

    monkeypatch.setattr(data_indexing, "NLPController", FailingController)
    task = FakeTaskInstance()

    with pytest.raises(Exception, match="cannot insert into VectoDb"):
        run(
            data_indexing._index_data_content(
                task,
                project_id=7,
                do_reset=0,
            )
        )

    assert task.states[-1]["state"] == "FAILURE"
    assert task.states[-1]["meta"]["signal"] == "insert_into_vector_db_error"
    assert engine.disposed is True
    assert vector_db.disconnected is True
