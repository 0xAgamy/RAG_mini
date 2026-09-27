from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from controllers.NLPController import NLPController
from stores.llm.templates.template_parser import TemplateParser


def run(awaitable):
    return asyncio.run(awaitable)


class FakeVectorDB:
    default_vector_size = 1536

    def __init__(self):
        self.create_calls: list[dict[str, Any]] = []
        self.insert_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.delete_calls: list[str] = []
        self.collection_info = SimpleNamespace(
            points=7,
            config={"distance": "COSINE"},
        )
        self.search_result = [SimpleNamespace(text="cached result", score=0.9)]

    async def create_collection(self, **kwargs):
        self.create_calls.append(kwargs)
        return True

    async def insert_many(self, **kwargs):
        self.insert_calls.append(kwargs)
        return True

    async def search_by_vector(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_result

    async def delete_collection(self, collection_name: str):
        self.delete_calls.append(collection_name)
        return True

    async def get_collection_info(self, collection_name: str):
        return self.collection_info


class FakeEmbeddingClient:
    def __init__(self):
        self.embedding_size = 384
        self.embed_calls: list[dict[str, Any]] = []
        self.embeddings = [[0.1, 0.2, 0.3]]

    def embed_text(self, text, document_type=None):
        self.embed_calls.append({"text": text, "document_type": document_type})
        return self.embeddings


class FakeGenerationClient:
    def __init__(self):
        self.enums = SimpleNamespace(SYSTEM=SimpleNamespace(value="system"))
        self.generated_prompts: list[dict[str, Any]] = []
        self.answer = "A grounded answer"

    def construct_prompt(self, prompt: str, role: str):
        return {"role": role, "content": prompt}

    def generate_text(self, prompt, chat_history, **kwargs):
        self.generated_prompts.append(
            {"prompt": prompt, "chat_history": chat_history, **kwargs}
        )
        return self.answer


class FakeTemplateParser:
    def get(self, group, key, values=None):
        values = values or {}
        if key == "system_prompt":
            return "SYSTEM"
        if key == "document_prompt":
            return f"DOC {values['doc_number']}: {values['chunk_text']}"
        if key == "footer_prompt":
            return f"QUESTION: {values['query']}"
        return None


def make_controller(
    test_settings,
):
    vector_db = FakeVectorDB()
    embedding_client = FakeEmbeddingClient()
    generation_client = FakeGenerationClient()
    controller = NLPController(
        vectordb_client=vector_db,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=FakeTemplateParser(),
    )
    return controller, vector_db, embedding_client, generation_client


def test_create_collection_name_uses_vector_size_and_project(
    test_settings,
):
    controller, vector_db, _, _ = make_controller(test_settings)

    assert controller.create_collection_name(17) == "collection_1536_17"
    assert vector_db.default_vector_size == 1536


def test_get_vector_db_collection_info_returns_json_serializable_data(
    test_settings,
):
    controller, vector_db, _, _ = make_controller(test_settings)
    project = SimpleNamespace(project_id=3)

    info = run(controller.get_vector_db_collection_info(project))

    assert info == {"points": 7, "config": {"distance": "COSINE"}}


def test_reset_vector_db_collection_deletes_expected_collection(
    test_settings,
):
    controller, vector_db, _, _ = make_controller(test_settings)
    project = SimpleNamespace(project_id=3)

    result = run(controller.reset_vector_db_collection(project))

    assert result is True
    assert vector_db.delete_calls == ["collection_1536_3"]


def test_index_into_vector_db_embeds_and_inserts_all_chunks(
    test_settings,
):
    controller, vector_db, embedding_client, _ = make_controller(test_settings)
    project = SimpleNamespace(project_id=9)
    chunks = [
        SimpleNamespace(chunk_text="first", chunk_metadata={"page": 1}),
        SimpleNamespace(chunk_text="second", chunk_metadata={"page": 2}),
    ]

    result = run(
        controller.index_into_vector_db(
            project=project,
            chunks=chunks,
            chunks_ids=[101, 102],
            do_reset=True,
        )
    )

    assert result is True
    assert embedding_client.embed_calls == [
        {"text": ["first", "second"], "document_type": "document"}
    ]
    assert vector_db.create_calls == [
        {
            "collection_name": "collection_1536_9",
            "embedding_size": 384,
            "do_reset": True,
        }
    ]
    assert vector_db.insert_calls == [
        {
            "collection_name": "collection_1536_9",
            "texts": ["first", "second"],
            "vectors": [[0.1, 0.2, 0.3]],
            "record_id": [101, 102],
            "metadata": [{"page": 1}, {"page": 2}],
        }
    ]


def test_search_vector_db_collection_uses_first_query_embedding(
    test_settings,
):
    controller, vector_db, embedding_client, _ = make_controller(test_settings)
    project = SimpleNamespace(project_id=4)

    result = run(
        controller.search_vector_db_collection(
            project=project,
            text="What is RAG?",
            limit=5,
        )
    )

    assert [(document.text, document.score) for document in result] == [
        ("cached result", 0.9)
    ]
    assert embedding_client.embed_calls == [
        {"text": "What is RAG?", "document_type": "query"}
    ]
    assert vector_db.search_calls == [
        {
            "collection_name": "collection_1536_4",
            "vector": [0.1, 0.2, 0.3],
            "limit": 5,
        }
    ]


def test_search_vector_db_collection_returns_false_without_embedding(
    test_settings,
):
    controller, vector_db, embedding_client, _ = make_controller(test_settings)
    embedding_client.embeddings = []
    project = SimpleNamespace(project_id=4)

    result = run(
        controller.search_vector_db_collection(
            project=project,
            text="unknown",
        )
    )

    assert result is False
    assert vector_db.search_calls == []


def test_answer_rag_question_builds_prompt_from_retrieved_documents(
    test_settings,
):
    controller, _, _, generation_client = make_controller(test_settings)
    project = SimpleNamespace(project_id=2)

    async def fake_search(**kwargs):
        assert kwargs == {
            "project": project,
            "text": "What is retrieval?",
            "limit": 3,
        }
        return [
            SimpleNamespace(text="RAG retrieves relevant context.", score=0.95),
            SimpleNamespace(text="The LLM uses that context.", score=0.80),
        ]

    controller.search_vector_db_collection = fake_search

    answer, prompt, history = run(
        controller.answer_rag_question(
            project=project,
            query="What is retrieval?",
            limit=3,
        )
    )

    assert answer == "A grounded answer"
    assert "DOC 1: RAG retrieves relevant context." in prompt
    assert "DOC 2: The LLM uses that context." in prompt
    assert "QUESTION: What is retrieval?" in prompt
    assert history == [{"role": "system", "content": "SYSTEM"}]
    assert generation_client.generated_prompts[0]["prompt"] == prompt
    assert generation_client.generated_prompts[0]["chat_history"] == history


def test_answer_rag_question_returns_empty_tuple_without_documents(
    test_settings,
):
    controller, _, _, _ = make_controller(test_settings)
    project = SimpleNamespace(project_id=2)

    async def no_results(**kwargs):
        return []

    controller.search_vector_db_collection = no_results

    assert run(
        controller.answer_rag_question(
            project=project,
            query="anything",
        )
    ) == (None, None, None)


def test_answer_rag_question_works_with_real_template_parser(test_settings):
    vector_db = FakeVectorDB()
    embedding_client = FakeEmbeddingClient()
    generation_client = FakeGenerationClient()
    controller = NLPController(
        vectordb_client=vector_db,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=TemplateParser(language="en"),
    )
    project = SimpleNamespace(project_id=2)

    async def fake_search(**kwargs):
        return [SimpleNamespace(text="Relevant context", score=0.9)]

    controller.search_vector_db_collection = fake_search

    answer, prompt, history = run(
        controller.answer_rag_question(
            project=project,
            query="What is RAG?",
        )
    )

    assert answer == "A grounded answer"
    assert isinstance(prompt, str)
    assert "Relevant context" in prompt
    assert "What is RAG?" in prompt
    assert history[0]["role"] == "system"
