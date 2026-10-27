import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.db.models import PolicyChunk
from app.rag.index import index_corpus
from app.rag.retrieve import search_policy_docs

ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus"


async def constant_embeddings(texts: list[str]) -> list[list[float]]:
    return [[1.0] + [0.0] * 383 for _ in texts]


async def test_indexing_is_idempotent_and_retains_other_versions(database) -> None:
    session, _ = database
    await session.execute(text("TRUNCATE policy_chunks"))
    await session.commit()
    assert await index_corpus(session, ROOT, embed=constant_embeddings) == 54
    session.add(
        PolicyChunk(
            product_code="MOT",
            clause_id="MOT-C01",
            clause_title="Previous",
            content="Earlier wording",
            corpus_version=2,
            embedding=[1.0] + [0.0] * 383,
        )
    )
    await session.commit()
    assert await index_corpus(session, ROOT, embed=constant_embeddings) == 54
    assert await session.scalar(select(func.count()).select_from(PolicyChunk)) == 55
    for product in ["ASP", "MOT", "TRM"]:
        count = await session.scalar(
            select(func.count())
            .select_from(PolicyChunk)
            .where(PolicyChunk.product_code == product, PolicyChunk.corpus_version == 1)
        )
        assert count == 18


async def test_changed_source_is_rejected_before_indexing(database, tmp_path) -> None:
    shutil.copytree(ROOT, tmp_path / "corpus")
    path = tmp_path / "corpus" / "source" / "ASP.md"
    path.write_text(path.read_text() + "\nUnverified change.\n")
    with pytest.raises(ValueError, match="checksum"):
        await index_corpus(database[0], tmp_path / "corpus", embed=constant_embeddings)


async def test_retrieval_filters_product_version_and_score_floor(database) -> None:
    session, _ = database
    await session.execute(text("TRUNCATE policy_chunks"))
    for code, version, title in [("ASP", 1, "Health"), ("MOT", 1, "Motor"), ("MOT", 2, "Future")]:
        session.add(
            PolicyChunk(
                product_code=code,
                clause_id=f"{code}-C01",
                clause_title=title,
                content=title,
                corpus_version=version,
                embedding=[1.0] + [0.0] * 383,
            )
        )
    await session.commit()
    chunks = await search_policy_docs(
        session, "question", "MOT", embed=constant_embeddings, use_cache=False
    )
    assert [chunk.clause_title for chunk in chunks] == ["Motor"]

    async def unrelated(texts: list[str]) -> list[list[float]]:
        return [[-1.0] + [0.0] * 383 for _ in texts]

    assert (
        await search_policy_docs(session, "nonsense", "MOT", embed=unrelated, use_cache=False) == []
    )
    with pytest.raises(ValueError):
        await search_policy_docs(session, "question", "UNKNOWN", embed=constant_embeddings)
