from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import settings
from ingest import embeddings


def test_embedding_batches_use_separate_provider_and_keep_input_order(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.embeddings.create.side_effect = [
        SimpleNamespace(data=[
            SimpleNamespace(index=index, embedding=[float(index)] * 3)
            for index in reversed(range(10))
        ]),
        SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[10.0] * 3)]),
    ]
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(embeddings, "OpenAI", factory)
    monkeypatch.setattr(settings, "embedding_api_key", "embedding-test-key")
    monkeypatch.setattr(settings, "embedding_base_url", "https://embedding.example/v1")
    monkeypatch.setattr(settings, "embedding_dimensions", 3)

    result = embeddings.embed_texts([str(index) for index in range(11)])

    assert result == [[float(index)] * 3 for index in range(11)]
    factory.assert_called_once_with(
        api_key="embedding-test-key", base_url="https://embedding.example/v1"
    )
    assert [len(call.kwargs["input"]) for call in client.embeddings.create.call_args_list] == [10, 1]
    for call in client.embeddings.create.call_args_list:
        assert call.kwargs["encoding_format"] == "float"
        assert call.kwargs["model"] == settings.embedding_model
        assert call.kwargs["dimensions"] == 3


@pytest.mark.parametrize("indices", [[0], [0, 0], [0, 2]])
def test_embedding_rejects_missing_or_duplicate_indices(monkeypatch, indices):
    client = MagicMock()
    client.__enter__.return_value = client
    client.embeddings.create.return_value.data = [
        SimpleNamespace(index=index, embedding=[0.0] * 1536) for index in indices
    ]
    monkeypatch.setattr(embeddings, "_client", lambda: client)

    with pytest.raises(ValueError, match="indices"):
        embeddings.embed_texts(["first", "second"])


def test_embedding_rejects_incompatible_dimensions(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.embeddings.create.return_value.data = [
        SimpleNamespace(index=0, embedding=[0.0] * 1024)
    ]
    monkeypatch.setattr(embeddings, "_client", lambda: client)

    with pytest.raises(ValueError, match="Expected embedding dimension 1536"):
        embeddings.embed_texts(["first"])
