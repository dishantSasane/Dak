import pytest
from sqlalchemy import func, select, text, update

from app.cache.semantic import lookup_answer, write_answer
from app.config import get_settings
from app.db.models import PolicyChunk, SemanticCache
from app.models.schemas import Chunk, Draft, DraftSentence, ValidationResult


async def embedding(texts: list[str]) -> list[list[float]]:
    return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture
async def cache_case(database):
    session, _ = database
    await session.execute(text("TRUNCATE semantic_cache, policy_chunks"))
    session.add(
        PolicyChunk(
            product_code="ASP",
            clause_id="ASP-C06",
            clause_title="Ambulance",
            content="Road ambulance allowance is Rs 3,500.",
            corpus_version=1,
            embedding=[1.0] + [0.0] * 383,
        )
    )
    await session.commit()
    draft = Draft(
        sentences=[
            DraftSentence(
                text="Road ambulance allowance is Rs 3,500.", kind="factual", cite="ASP-C06"
            )
        ]
    )
    chunks = [
        Chunk(
            clause_id="ASP-C06",
            clause_title="Ambulance",
            content="Road ambulance allowance is Rs 3,500.",
            score=0.9,
        )
    ]
    return session, draft, chunks


@pytest.mark.parametrize(
    "customer,personal,passed", [(True, False, True), (False, True, True), (False, False, False)]
)
async def test_customer_or_unvalidated_answers_never_cached(cache_case, customer, personal, passed):
    session, draft, chunks = cache_case
    stored = await write_answer(
        session,
        "question",
        "ASP",
        draft,
        ValidationResult(passed=passed),
        chunks,
        used_customer_tools=customer,
        numbers_from_policy_record=personal,
        embed=embedding,
    )
    assert not stored
    assert await session.scalar(select(func.count()).select_from(SemanticCache)) == 0


async def test_hits_rehydrate_current_corpus_and_version_bump_misses(cache_case, monkeypatch):
    session, draft, chunks = cache_case
    assert await write_answer(
        session,
        "ambulance?",
        "ASP",
        draft,
        ValidationResult(passed=True),
        chunks,
        used_customer_tools=False,
        numbers_from_policy_record=False,
        embed=embedding,
    )
    hit = await lookup_answer(session, "ambulance allowance?", "ASP", embed=embedding)
    assert hit is not None and hit.draft == draft
    assert hit.chunks[0].clause_id == "ASP-C06"
    assert await lookup_answer(session, "ambulance?", "MOT", embed=embedding) is None
    monkeypatch.setattr(get_settings(), "CORPUS_VERSION", 2)
    assert await lookup_answer(session, "ambulance?", "ASP", embed=embedding) is None
    monkeypatch.setattr(get_settings(), "CORPUS_VERSION", 1)
    await session.execute(update(PolicyChunk).values(content="Unversioned changed wording"))
    await session.commit()
    assert await lookup_answer(session, "ambulance?", "ASP", embed=embedding) is None


async def test_phantom_or_mismatched_citation_is_not_cached(cache_case):
    session, draft, chunks = cache_case
    draft.sentences[0].cite = "ASP-C99"
    assert not await write_answer(
        session,
        "question",
        "ASP",
        draft,
        ValidationResult(passed=True),
        chunks,
        used_customer_tools=False,
        numbers_from_policy_record=False,
        embed=embedding,
    )


async def test_customer_echo_in_courtesy_or_procedural_text_never_cached(cache_case):
    session, draft, chunks = cache_case
    draft.sentences.insert(
        0, DraftSentence(text="Hello Alice, policy ASP-2024-1234.", kind="courtesy")
    )
    assert not await write_answer(
        session,
        "question",
        "ASP",
        draft,
        ValidationResult(passed=True),
        chunks,
        used_customer_tools=False,
        numbers_from_policy_record=False,
        embed=embedding,
    )
