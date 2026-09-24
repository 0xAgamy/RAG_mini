from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
from fastapi import APIRouter, FastAPI
from pytest import MonkeyPatch

from helpers.config import get_settings
from routes import base as base_routes
from routes import data as data_routes
from routes import nlp as nlp_routes


def make_request(
    app: FastAPI,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make an ASGI request without starting external service lifespans."""

    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(request())


def make_app(router: APIRouter) -> FastAPI:
    app = FastAPI()
    # Routes read these attributes directly from ``request.app`` rather than
    # through ``app.state``.  Supply harmless placeholders by default so each
    # test can override only the boundary it exercises.
    app.db_client = object()
    app.storage_client = object()
    app.vectordb_client = object()
    app.generation_client = object()
    app.embedding_client = object()
    app.template_parser = object()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(
        APP_NAME="RAG-mini-test",
        APP_VERSION="test",
        FILE_ALLOWED_TYPES=["text/plain", "application/pdf"],
        FILE_MAX_SIZE=10,
    )
    return app


def response_json(response: httpx.Response) -> dict[str, Any]:
    return json.loads(response.content)


def test_welcome_endpoint_returns_application_metadata():
    app = make_app(base_routes.base_router)

    response = make_request(app, "GET", "/api/v1/")

    assert response.status_code == 200
    assert response_json(response) == {"app": "RAG-mini-test", "version": "test"}


def test_send_reports_endpoint_queues_task(
    monkeypatch: MonkeyPatch,
):
    app = make_app(base_routes.base_router)
    task = SimpleNamespace(id="report-task-1")

    def fake_delay(**kwargs):
        assert kwargs == {"mail_waits_seconds": 3}
        return task

    monkeypatch.setattr(base_routes.send_email_reports, "delay", fake_delay)

    response = make_request(app, "GET", "/api/v1/send_reports")

    assert response.status_code == 200
    assert response_json(response) == {"success": True, "task_id": "report-task-1"}


def test_upload_endpoint_validates_stores_and_returns_file_id(
    test_settings: SimpleNamespace,
    monkeypatch: MonkeyPatch,
):
    app = make_app(data_routes.data_router)
    app.db_client = object()
    storage_client = SimpleNamespace(
        upload_file=AsyncMock(return_value="documents/generated.txt"),
        file_size=AsyncMock(return_value=0.001),
    )
    app.storage_client = storage_client

    project = SimpleNamespace(project_id=42)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    asset_model = SimpleNamespace(
        create_asset=AsyncMock(return_value=SimpleNamespace(asset_id=99))
    )
    monkeypatch.setattr(
        data_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(
        data_routes.AssetModel,
        "create_instance",
        AsyncMock(return_value=asset_model),
    )

    response = make_request(
        app,
        "POST",
        "/api/v1/data/upload/42",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    assert response_json(response)["signal"] == "file_uploaded_successfully"
    assert response_json(response)["file_id"] == "99"

    storage_client.upload_file.assert_awaited_once()
    uploaded_file, object_name = storage_client.upload_file.await_args.args
    assert uploaded_file.filename == "notes.txt"
    assert object_name.startswith("documents/")
    assert object_name.endswith(".txt")

    asset = asset_model.create_asset.await_args.args[0]
    assert asset.asset_project_id == 42
    assert asset.asset_type == "file"
    assert asset.asset_name == "documents/generated.txt"
    assert asset.asset_size == 0.001


def test_upload_endpoint_rejects_unsupported_type_before_storage(
    test_settings: SimpleNamespace,
    monkeypatch: MonkeyPatch,
):
    app = make_app(data_routes.data_router)
    app.db_client = object()
    storage_client = SimpleNamespace(
        upload_file=AsyncMock(),
        file_size=AsyncMock(),
    )
    app.storage_client = storage_client

    project = SimpleNamespace(project_id=42)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    monkeypatch.setattr(
        data_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )

    response = make_request(
        app,
        "POST",
        "/api/v1/data/upload/42",
        files={"file": ("archive.zip", b"not-a-document", "application/zip")},
    )

    assert response.status_code == 400
    assert response_json(response) == {"signal": "file_type_not_supported"}
    storage_client.upload_file.assert_not_awaited()


def test_process_endpoint_forwards_request_to_celery(
    monkeypatch: MonkeyPatch,
):
    app = make_app(data_routes.data_router)
    task = SimpleNamespace(id="process-task-1")

    def fake_delay(**kwargs):
        assert kwargs == {
            "project_id": 42,
            "file_id": "asset-1",
            "chunk_size": 120,
            "overlap_size": 10,
            "do_reset": 1,
        }
        return task

    monkeypatch.setattr(data_routes.process_project_file, "delay", fake_delay)

    response = make_request(
        app,
        "POST",
        "/api/v1/data/process/42",
        json={
            "file_id": "asset-1",
            "chunk_size": 120,
            "overlap_size": 10,
            "do_reset": 1,
        },
    )

    assert response.status_code == 200
    # This is the current wire contract; a future API revision can correct the
    # historical ``singal`` spelling without changing the task behavior.
    assert response_json(response) == {
        "singal": "process",
        "task_id": "process-task-1",
    }


def test_index_push_endpoint_forwards_reset_option(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    task = SimpleNamespace(id="index-task-1")

    def fake_delay(**kwargs):
        assert kwargs == {"project_id": 7, "do_reset": 1}
        return task

    monkeypatch.setattr(nlp_routes.index_data_content, "delay", fake_delay)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/push/7",
        json={"do_reset": 1},
    )

    assert response.status_code == 200
    assert response_json(response) == {
        "signal": "processing_success",
        "task_id": "index-task-1",
    }


def test_index_info_endpoint_returns_collection_info(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    project = SimpleNamespace(project_id=7)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    controller = SimpleNamespace(
        get_vector_db_collection_info=AsyncMock(
            return_value={"points": 4}
        )
    )
    monkeypatch.setattr(
        nlp_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(nlp_routes, "NLPController", lambda **kwargs: controller)

    response = make_request(app, "GET", "/api/v1/nlp/index/info/7")

    assert response.status_code == 200
    assert response_json(response) == {
        "signal": "vectordb_collection_retrieved",
        "collection_info": {"points": 4},
    }


def test_search_endpoint_returns_search_results(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    project = SimpleNamespace(project_id=7)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    result = SimpleNamespace(
        model_dump=lambda: {"text": "retrieved", "score": 0.99}
    )
    controller = SimpleNamespace(
        search_vector_db_collection=AsyncMock(return_value=[result])
    )
    monkeypatch.setattr(
        nlp_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(nlp_routes, "NLPController", lambda **kwargs: controller)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/search/7",
        json={"text": "question", "limit": 4},
    )

    assert response.status_code == 200
    assert response_json(response) == {
        "signal": "vector_search_success",
        "search_results": [{"text": "retrieved", "score": 0.99}],
    }
    controller.search_vector_db_collection.assert_awaited_once()
    assert controller.search_vector_db_collection.await_args.kwargs == {
        "project": project,
        "text": "question",
        "limit": 4,
    }


def test_search_endpoint_returns_bad_request_without_results(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    project = SimpleNamespace(project_id=7)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    controller = SimpleNamespace(
        search_vector_db_collection=AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        nlp_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(nlp_routes, "NLPController", lambda **kwargs: controller)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/search/7",
        json={"text": "question"},
    )

    assert response.status_code == 400
    assert response_json(response) == {"signal": "vector_search_error"}


def test_ask_endpoint_returns_generated_answer(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    project = SimpleNamespace(project_id=7)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    controller = SimpleNamespace(
        answer_rag_question=AsyncMock(
            return_value=("An answer", "A prompt", [{"role": "system"}])
        )
    )
    monkeypatch.setattr(
        nlp_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(nlp_routes, "NLPController", lambda **kwargs: controller)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/ask/7",
        json={"text": "question", "limit": 2},
    )

    body = response_json(response)
    assert response.status_code == 200
    assert body["signal"] == "rag_answer_success"
    # The current API uses a trailing space in this legacy response key.  The
    # value is asserted without coupling the test to that spelling.
    assert body.get("answer", body.get("answer ")) == "An answer"
    assert body["full_prompt"] == "A prompt"
    assert body["chat_history"] == [{"role": "system"}]
    controller.answer_rag_question.assert_awaited_once()
    assert controller.answer_rag_question.await_args.kwargs == {
        "project": project,
        "query": "question",
        "limit": 2,
    }


def test_ask_endpoint_returns_bad_request_when_generation_fails(
    monkeypatch: MonkeyPatch,
):
    app = make_app(nlp_routes.nlp_router)
    project = SimpleNamespace(project_id=7)
    project_model = SimpleNamespace(
        get_project_or_create_one=AsyncMock(return_value=project)
    )
    controller = SimpleNamespace(
        answer_rag_question=AsyncMock(return_value=(None, None, None))
    )
    monkeypatch.setattr(
        nlp_routes.ProjectModel,
        "create_instance",
        AsyncMock(return_value=project_model),
    )
    monkeypatch.setattr(nlp_routes, "NLPController", lambda **kwargs: controller)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/ask/7",
        json={"text": "question"},
    )

    assert response.status_code == 400
    assert response_json(response) == {"signal": "rag_answer_error"}


def test_nlp_request_schema_rejects_missing_text():
    app = make_app(nlp_routes.nlp_router)

    response = make_request(
        app,
        "POST",
        "/api/v1/nlp/index/search/7",
        json={},
    )

    assert response.status_code == 422
