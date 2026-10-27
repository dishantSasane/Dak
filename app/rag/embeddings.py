"""The specified local 384-dimensional CPU embedder; no model/API inference calls."""

from __future__ import annotations

import asyncio
import math
import threading
from collections.abc import Awaitable, Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DIMENSIONS = 384
Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]
_MODEL_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    from fastembed import TextEmbedding

    cache = Path(__file__).resolve().parents[2] / ".cache" / "embeddings"
    return TextEmbedding(
        MODEL_NAME,
        cache_dir=str(cache),
        threads=1,
    )


def validate_embeddings(vectors: list[list[float]], expected: int) -> None:
    if len(vectors) != expected:
        raise ValueError("Embedding count does not match text count")
    for vector in vectors:
        if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
            raise ValueError("Embedding must contain 384 finite values")
        if sum(value * value for value in vector) == 0:
            raise ValueError("Embedding must not be a zero vector")


def _encode(texts: list[str]) -> list[list[float]]:
    with _MODEL_LOCK:
        # Keep peak RAM low for small instances such as Render's 512 MiB
        # free web service. Corpus bootstrap can embed many clauses at once.
        vectors = []
        for embedding in _model().embed(texts, batch_size=1, parallel=1):
            vector = [float(value) for value in embedding]
            norm = math.sqrt(sum(value * value for value in vector))
            if norm:
                vector = [value / norm for value in vector]
            vectors.append(vector)
    validate_embeddings(vectors, len(texts))
    return vectors


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(_encode, texts)
