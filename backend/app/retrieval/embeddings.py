"""Query embedding using the same provider and model as document ingestion."""

from __future__ import annotations

from openai import OpenAI

from app.config import settings


def _client() -> OpenAI:
    return OpenAI(
        api_key=settings.embedding_api_key, base_url=settings.embedding_base_url
    )


def embed_query(text: str) -> list[float]:
    with _client() as client:
        response = client.embeddings.create(
            input=[text],
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            encoding_format="float",
        )
    if len(response.data) != 1 or response.data[0].index != 0:
        raise ValueError("Expected one query embedding with index 0")
    embedding = response.data[0].embedding
    expected_dims = settings.embedding_dimensions
    if len(embedding) != expected_dims:
        raise ValueError(
            f"Expected embedding dimension {expected_dims}, got {len(embedding)}"
        )
    return embedding
