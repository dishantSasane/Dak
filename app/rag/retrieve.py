"""Product/version-restricted cosine retrieval with a six-hour Redis cache."""

from __future__ import annotations

import hashlib
import json
import logging

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import PolicyChunk
from app.models.schemas import Chunk
from app.rag.embeddings import Embedder, embed_texts, validate_embeddings
from app.rag.ingest import PRODUCTS
from app.redis_client import cache_get_json, cache_set_json

logger = logging.getLogger(__name__)


def normalize_question(question: str) -> str:
    return " ".join(question.lower().split())


async def search_policy_docs(
    session: AsyncSession,
    question: str,
    product_code: str,
    k: int = 5,
    *,
    embed: Embedder = embed_texts,
    use_cache: bool = True,
) -> list[Chunk]:
    settings = get_settings()
    if product_code not in PRODUCTS or not 1 <= k <= 20:
        raise ValueError("A known product and k between 1 and 20 are required")
    normalized = normalize_question(question)
    if not normalized:
        return []
    signature = json.dumps(
        [normalized, product_code, settings.CORPUS_VERSION, k, settings.RETRIEVAL_SCORE_FLOOR]
    )
    key = "retrieval:" + hashlib.sha256(signature.encode()).hexdigest()
    if use_cache:
        try:
            cached = await cache_get_json(key)
            if cached is not None:
                return [Chunk.model_validate(row) for row in cached]
        except RedisError:
            logger.warning("retrieval cache unavailable; querying PostgreSQL")
    vectors = await embed([normalized])
    validate_embeddings(vectors, 1)
    distance = PolicyChunk.embedding.cosine_distance(vectors[0])
    rows = (
        await session.execute(
            select(PolicyChunk, (1 - distance).label("score"))
            .where(
                PolicyChunk.product_code == product_code,
                PolicyChunk.corpus_version == settings.CORPUS_VERSION,
                1 - distance >= settings.RETRIEVAL_SCORE_FLOOR,
            )
            .order_by(distance, PolicyChunk.clause_id)
            .limit(k)
        )
    ).all()
    chunks = [
        Chunk(
            clause_id=row.clause_id,
            clause_title=row.clause_title,
            content=row.content,
            score=float(score),
        )
        for row, score in rows
    ]
    if use_cache:
        try:
            await cache_set_json(key, [chunk.model_dump() for chunk in chunks], 6 * 3600)
        except RedisError:
            logger.warning("retrieval cache write failed")
    return chunks
