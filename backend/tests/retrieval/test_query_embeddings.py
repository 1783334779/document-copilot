from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.retrieval import embeddings


def test_query_uses_document_embedding_provider_and_float_encoding(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    vector = [0.5] * 1536
    client.embeddings.create.return_value.data = [
        SimpleNamespace(index=0, embedding=vector)
    ]
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(embeddings, "OpenAI", factory)
    monkeypatch.setattr(settings, "embedding_api_key", "embedding-test-key")
    monkeypatch.setattr(settings, "embedding_base_url", "https://embedding.example/v1")

    assert embeddings.embed_query("annual revenue") == vector
    factory.assert_called_once_with(
        api_key="embedding-test-key", base_url="https://embedding.example/v1"
    )
    client.embeddings.create.assert_called_once_with(
        input=["annual revenue"],
        model=settings.embedding_model,
        dimensions=1536,
        encoding_format="float",
    )


def test_query_rejects_incompatible_dimensions(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.embeddings.create.return_value.data = [
        SimpleNamespace(index=0, embedding=[0.0] * 1024)
    ]
    monkeypatch.setattr(embeddings, "_client", lambda: client)

    with pytest.raises(ValueError, match="Expected embedding dimension 1536"):
        embeddings.embed_query("annual revenue")
