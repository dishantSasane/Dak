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
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
DIMENSIONS = 384
Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]
_MODEL_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    cache = Path(__file__).resolve().parents[2] / ".cache" / "embeddings"
    return SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device="cpu",
        cache_folder=str(cache),
        trust_remote_code=False,
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
        vectors = (
            _model().encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
        )
    validate_embeddings(vectors, len(texts))
    return vectors


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(_encode, texts)
