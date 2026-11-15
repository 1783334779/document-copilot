"""Embedding generation for document chunks through an OpenAI-compatible API."""

from __future__ import annotations

from openai import OpenAI

from app.config import settings

EMBED_BATCH_SIZE = settings.embedding_batch_size


def _client() -> OpenAI:
    return OpenAI(
        api_key=settings.embedding_api_key, base_url=settings.embedding_base_url
    )


def embed_texts(texts: list[str], *, batch_size: int = EMBED_BATCH_SIZE) -> list[list[float]]:
    if not texts:
        return []

    expected_dims = settings.embedding_dimensions
    vectors: list[list[float]] = []

    with _client() as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.embeddings.create(
                input=batch,
                model=settings.embedding_model,
                dimensions=expected_dims,
                encoding_format="float",
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError(
                    "Embedding response indices do not match the input batch"
                )
            for item in ordered:
                embedding = item.embedding
                if len(embedding) != expected_dims:
                    raise ValueError(
                        f"Expected embedding dimension {expected_dims}, got {len(embedding)}"
                    )
                vectors.append(embedding)

    return vectors
