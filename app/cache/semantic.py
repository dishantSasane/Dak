"""Generic validated answers only, with corpus/version-scoped citation rehydration.

The caller must still route cache hits through the deterministic validator.
No cached clause is accepted without matching the current database wording.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import PolicyChunk, SemanticCache
from app.models.schemas import Chunk, Draft, ValidationResult
from app.rag.embeddings import Embedder, embed_texts, validate_embeddings
from app.rag.ingest import PRODUCTS
from app.rag.retrieve import normalize_question


@dataclass(frozen=True)
class CachedAnswer:
    draft: Draft
    chunks: list[Chunk]


async def _current_chunks(
    session: AsyncSession,
    product_code: str,
    citations: list[Chunk],
) -> list[Chunk] | None:
    if not citations:
        return None
    identifiers = {chunk.clause_id for chunk in citations}
    rows = (
        await session.scalars(
            select(PolicyChunk).where(
                PolicyChunk.product_code == product_code,
                PolicyChunk.corpus_version == get_settings().CORPUS_VERSION,
                PolicyChunk.clause_id.in_(identifiers),
            )
        )
    ).all()
    current = {row.clause_id: row for row in rows}
    if set(current) != identifiers:
        return None
    result = []
    for chunk in citations:
        row = current[chunk.clause_id]
        if row.content != chunk.content or row.clause_title != chunk.clause_title:
            return None
        result.append(
            Chunk(
                clause_id=row.clause_id,
                clause_title=row.clause_title,
                content=row.content,
                score=chunk.score,
            )
        )
    return result


def generic_sentences(draft: Draft, chunks: list[Chunk]) -> bool:
    """Admit only corpus excerpts or fixed courtesy text to the global cache.

    A grounded paraphrase can still be reviewed, but cannot introduce customer
    names, identifiers or sender-supplied prose into a globally reusable answer.
    """
    courtesy = {"hello", "thanks for writing in", "thank you for contacting us", "regards"}
    available = {chunk.clause_id: " ".join(chunk.content.casefold().split()) for chunk in chunks}
    for sentence in draft.sentences:
        text = " ".join(sentence.text.casefold().split()).rstrip(".!?")
        if sentence.kind == "courtesy" and text in courtesy:
            continue
        if not text or not sentence.cite or text not in available.get(sentence.cite, ""):
            return False
    return True


async def write_answer(
    session: AsyncSession,
    question: str,
    product_code: str,
    draft: Draft,
    validation: ValidationResult,
    chunks: list[Chunk],
    *,
    used_customer_tools: bool,
    numbers_from_policy_record: bool,
    embed: Embedder = embed_texts,
) -> bool:
    if (
        product_code not in PRODUCTS
        or not validation.passed
        or validation.violations
        or used_customer_tools
        or numbers_from_policy_record
        or draft.cannot_answer
        or not draft.sentences
        or not normalize_question(question)
    ):
        return False
    required = [
        sentence for sentence in draft.sentences if sentence.kind in ("factual", "commitment")
    ]
    if not required or any(sentence.cite is None for sentence in required):
        return False
    available = {chunk.clause_id: chunk for chunk in chunks}
    identifiers = {sentence.cite for sentence in draft.sentences if sentence.cite}
    if any(identifier not in available for identifier in identifiers):
        return False
    citations = [available[identifier] for identifier in sorted(identifiers)]
    if await _current_chunks(session, product_code, citations) is None:
        return False
    if not generic_sentences(draft, citations):
        return False
    normalized = normalize_question(question)
    vectors = await embed([normalized])
    validate_embeddings(vectors, 1)
    # Serialize identical-question writes without adding a new DB constraint.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"semantic:{product_code}:{get_settings().CORPUS_VERSION}:{normalized}"},
    )
    existing = await session.scalar(
        select(SemanticCache)
        .where(
            SemanticCache.question_norm == normalized,
            SemanticCache.product_code == product_code,
            SemanticCache.corpus_version == get_settings().CORPUS_VERSION,
        )
        .limit(1)
    )
    values = dict(
        question_norm=normalized,
        question_emb=vectors[0],
        product_code=product_code,
        corpus_version=get_settings().CORPUS_VERSION,
        answer_sentences=[sentence.model_dump() for sentence in draft.sentences],
        citations=[chunk.model_dump() for chunk in citations],
    )
    if existing is None:
        session.add(SemanticCache(**values))
    else:
        for name, value in values.items():
            setattr(existing, name, value)
    await session.commit()
    return True


async def lookup_answer(
    session: AsyncSession,
    question: str,
    product_code: str,
    *,
    embed: Embedder = embed_texts,
) -> CachedAnswer | None:
    if product_code not in PRODUCTS or not normalize_question(question):
        return None
    vectors = await embed([normalize_question(question)])
    validate_embeddings(vectors, 1)
    settings = get_settings()
    distance = SemanticCache.question_emb.cosine_distance(vectors[0])
    candidates = (
        await session.scalars(
            select(SemanticCache)
            .where(
                SemanticCache.product_code == product_code,
                SemanticCache.corpus_version == settings.CORPUS_VERSION,
                1 - distance >= settings.SEMANTIC_CACHE_THRESHOLD,
            )
            .order_by(distance, SemanticCache.id)
            .limit(5)
        )
    ).all()
    for candidate in candidates:
        citations = [Chunk.model_validate(item) for item in candidate.citations]
        current = await _current_chunks(session, product_code, citations)
        if current is None:
            continue
        draft = Draft.model_validate({"sentences": candidate.answer_sentences})
        if not generic_sentences(draft, current):
            continue
        identifiers = {chunk.clause_id for chunk in current}
        if any(
            sentence.kind in ("factual", "commitment") and sentence.cite not in identifiers
            for sentence in draft.sentences
        ):
            continue
        if any(sentence.cite and sentence.cite not in identifiers for sentence in draft.sentences):
            continue
        await session.execute(
            update(SemanticCache)
            .where(SemanticCache.id == candidate.id)
            .values(hit_count=SemanticCache.hit_count + 1, last_hit_at=func.now())
        )
        await session.commit()
        return CachedAnswer(draft=draft, chunks=current)
    return None
