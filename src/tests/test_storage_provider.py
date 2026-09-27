from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace

import pytest

from stores.storage.providers.MinioStorageProvider import MinIoStorage


minio_module = importlib.import_module(
    "stores.storage.providers.MinioStorageProvider"
)


class FakeMinioClient:
    def __init__(self):
        self.buckets: list[str] = []
        self.uploads: list[dict] = []
        self.deleted: list[str] = []
        self.downloads: list[tuple[str, str, str]] = []

    def list_buckets(self):
        return self.buckets

    def make_bucket(self, bucket):
        self.buckets.append(bucket)

    def put_object(self, bucket, object_name, file_object, **kwargs):
        self.uploads.append(
            {
                "bucket": bucket,
                "object_name": object_name,
                "content_type": kwargs["content_type"],
            }
        )
        return SimpleNamespace()

    def stat_object(self, bucket, object_name):
        if object_name == "missing":
            raise minio_module.S3Error(
                "missing", "not-found", "missing", None, None, None
            )
        return SimpleNamespace(size=2_000_000)

    def remove_object(self, bucket, object_name):
        self.deleted.append(object_name)
        return SimpleNamespace()

    def fget_object(self, bucket, object_name, destination):
        self.downloads.append((bucket, object_name, destination))
        return SimpleNamespace()

    def get_object(self, bucket, object_name):
        class Response:
            def read(inner_self):
                return b"stored content"

            def close(inner_self):
                pass

            def release_conn(inner_self):
                pass

        return Response()


def make_storage(monkeypatch: pytest.MonkeyPatch, client: FakeMinioClient):
    monkeypatch.setattr(minio_module, "Minio", lambda *args, **kwargs: client)
    return MinIoStorage(
        SimpleNamespace(
            MINIO_ENDPOINT="localhost:9000",
            MINIO_ROOT_USER="user",
            MINIO_ROOT_PASSWORD="password",
            MINIO_BUCKET_NAME="documents",
        )
    )


def test_minio_upload_creates_bucket_when_client_has_none(
    monkeypatch: pytest.MonkeyPatch,
):
    client = FakeMinioClient()
    storage = make_storage(monkeypatch, client)
    file_object = SimpleNamespace()
    file_object.seek = lambda position: setattr(file_object, "position", position)

    class FakeUpload:
        def __init__(self):
            self.file = file_object
            self.content_type = "text/plain"

        def seek(self, position):
            file_object.position = position

    result = asyncio.run(
        storage.upload_file(FakeUpload(), "documents/notes.txt")
    )

    assert result == "documents/notes.txt"
    assert client.buckets == ["documents"]
    assert client.uploads[0]["object_name"] == "documents/notes.txt"
    assert client.uploads[0]["content_type"] == "text/plain"


def test_minio_size_and_content_helpers_return_values(
    monkeypatch: pytest.MonkeyPatch,
):
    client = FakeMinioClient()
    storage = make_storage(monkeypatch, client)

    assert asyncio.run(storage.file_size("documents/notes.txt")) == 2.0
    assert asyncio.run(storage.get_file_content("documents/notes.txt")) == b"stored content"


def test_minio_delete_returns_false_for_s3_error(
    monkeypatch: pytest.MonkeyPatch,
):
    class FailingClient(FakeMinioClient):
        def remove_object(self, bucket, object_name):
            raise minio_module.S3Error(
                "error", "error", "error", None, None, None
            )

    client = FailingClient()
    storage = make_storage(monkeypatch, client)

    assert asyncio.run(storage.delete_file("documents/notes.txt")) is False
