from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from stores.llm.LLMEnums import DocumentTypeEnum
from stores.llm.providers import CoHereProvider, OpenAIProvider


class FakeOpenAIClient:
    def __init__(self):
        self.generation_calls: list[dict] = []
        self.embedding_calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create_chat))
        self.embeddings = SimpleNamespace(create=self.create_embedding)

    def create_chat(self, **kwargs):
        self.generation_calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="generated"))]
        )

    def create_embedding(self, **kwargs):
        self.embedding_calls.append(kwargs)
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
        )


class FakeCohereClient:
    def __init__(self):
        self.chat_calls: list[dict] = []
        self.embedding_calls: list[dict] = []

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content=[SimpleNamespace(text="cohere answer")])
        )

    def embed(self, **kwargs):
        self.embedding_calls.append(kwargs)
        return SimpleNamespace(embeddings=SimpleNamespace(float=[[0.4, 0.5]]))


def test_openai_provider_generates_and_embeds(monkeypatch: pytest.MonkeyPatch):
    client = FakeOpenAIClient()
    openai_module = importlib.import_module("stores.llm.providers.OpenAIProvider")
    monkeypatch.setattr(
        openai_module,
        "OpenAI",
        lambda **kwargs: client,
    )

    provider = OpenAIProvider(
        api_key="test-key",
        base_url="https://example.invalid",
        default_input_max_characters=20,
        default_generation_max_output_tokens=50,
        default_generation_temperature=0.3,
    )
    provider.set_generation_model("generation-model")
    provider.set_embedding_model("embedding-model", 3)

    assert provider.generate_text("a" * 30, chat_history=[]) == "generated"
    assert provider.embed_text("hello") == [[0.1, 0.2, 0.3]]

    assert client.generation_calls[0]["model"] == "generation-model"
    assert client.generation_calls[0]["messages"][-1]["role"] == "user"
    assert len(client.generation_calls[0]["messages"][-1]["content"]) == 20
    assert client.embedding_calls[0] == {
        "input": ["hello"],
        "model": "embedding-model",
    }


def test_cohere_provider_uses_query_input_type(monkeypatch: pytest.MonkeyPatch):
    client = FakeCohereClient()
    cohere_module = __import__(
        "stores.llm.providers.CoHereProvider",
        fromlist=["cohere"],
    )
    monkeypatch.setattr(cohere_module, "cohere", SimpleNamespace(ClientV2=lambda **kwargs: client))

    provider = CoHereProvider(
        api_key="test-key",
        default_input_max_characters=100,
        default_generation_max_output_tokens=20,
        default_generation_temperature=0.4,
    )
    provider.set_generation_model("command-model")
    provider.set_embedding_model("embed-model", 2)

    assert provider.generate_text("question", chat_history=[]) == "cohere answer"
    assert provider.embed_text("question", DocumentTypeEnum.QUERY.value) == [
        [0.4, 0.5]
    ]
    assert client.chat_calls[0]["model"] == "command-model"
    assert client.embedding_calls[0]["input_type"] == "search_query"
    assert client.embedding_calls[0]["texts"] == ["question"]
