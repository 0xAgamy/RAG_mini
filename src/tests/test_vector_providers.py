from __future__ import annotations

import asyncio
from types import SimpleNamespace

from stores.vectordb.providers.QdrantDBProvider import QdrantDBProvider


def run(awaitable):
    return asyncio.run(awaitable)


class FakeQdrantClient:
    def __init__(self, exists_values=None):
        self.exists_values = iter(exists_values or [])
        self.deleted: list[str] = []
        self.created: list[dict] = []
        self.uploads: list[dict] = []
        self.query_result = None

    def collection_exists(self, collection_name):
        try:
            return next(self.exists_values)
        except StopIteration:
            return True

    def delete_collection(self, collection_name):
        self.deleted.append(collection_name)
        return True

    def create_collection(self, **kwargs):
        self.created.append(kwargs)
        return True

    def upload_collection(self, **kwargs):
        self.uploads.append(kwargs)
        return True

    def query_points(self, **kwargs):
        return self.query_result


def make_provider(client: FakeQdrantClient) -> QdrantDBProvider:
    provider = QdrantDBProvider(
        db_client="http://qdrant.test",
        default_vector_size=384,
        distance_method="COSINE",
    )
    provider.client = client
    return provider


def test_qdrant_delete_collection_only_deletes_when_collection_exists():
    client = FakeQdrantClient(exists_values=[False])
    provider = make_provider(client)

    result = run(provider.delete_collection("collection_384_1"))

    assert result is None
    assert client.deleted == []


def test_qdrant_create_collection_resets_and_creates_missing_collection():
    client = FakeQdrantClient(exists_values=[True, False])
    provider = make_provider(client)

    result = run(
        provider.create_collection(
            collection_name="collection_384_1",
            embedding_size=384,
            do_reset=True,
        )
    )

    assert result is True
    assert client.deleted == ["collection_384_1"]
    assert client.created[0]["collection_name"] == "collection_384_1"
    assert client.created[0]["vectors_config"].size == 384


def test_qdrant_create_collection_returns_false_for_existing_collection():
    client = FakeQdrantClient(exists_values=[True])
    provider = make_provider(client)

    result = run(
        provider.create_collection(
            collection_name="collection_384_1",
            embedding_size=384,
        )
    )

    assert result is False
    assert client.created == []


def test_qdrant_insert_many_batches_payloads_and_waits():
    client = FakeQdrantClient()
    provider = make_provider(client)

    result = run(
        provider.insert_many(
            collection_name="collection_384_1",
            texts=["a", "b", "c"],
            vectors=[[1], [2], [3]],
            metadata=[{"page": 1}, {"page": 2}, {"page": 3}],
            record_id=[101, 102, 103],
            batch_size=2,
        )
    )

    assert result is True
    assert len(client.uploads) == 2
    assert client.uploads[0]["ids"] == [101, 102]
    assert client.uploads[1]["ids"] == [103]
    assert client.uploads[0]["payload"][0] == {
        "text": "a",
        "metadata": {"page": 1},
    }
    assert all(upload["wait"] is True for upload in client.uploads)


def test_qdrant_search_returns_retrieved_documents():
    client = FakeQdrantClient()
    client.query_result = SimpleNamespace(
        points=[
            SimpleNamespace(score=0.9, payload={"text": "first"}),
            SimpleNamespace(score=0.7, payload={"text": "second"}),
        ]
    )
    provider = make_provider(client)

    result = run(
        provider.search_by_vector(
            collection_name="collection_384_1",
            vector=[0.1, 0.2],
            limit=2,
        )
    )

    assert [(document.text, document.score) for document in result] == [
        ("first", 0.9),
        ("second", 0.7),
    ]


def test_qdrant_insert_one_rejects_missing_collection():
    client = FakeQdrantClient(exists_values=[False])
    provider = make_provider(client)

    result = run(
        provider.insert_one(
            collection_name="missing",
            text="text",
            vector=[1.0],
        )
    )

    assert result is False
    assert client.uploads == []
