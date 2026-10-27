"""Initialize the Render demo database without duplicating existing data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Claim, Grievance, Policy, PolicyChunk
from app.db.session import get_engine, get_sessionmaker
from app.rag.index import index_corpus
from scripts.seed import load

ROOT = Path(__file__).resolve().parents[1]


async def bootstrap() -> None:
    seeds = {
        "policies": json.loads((ROOT / "data/seeds/policies.json").read_text()),
        "claims": json.loads((ROOT / "data/seeds/claims.json").read_text()),
        "grievances": json.loads((ROOT / "data/seeds/grievances.json").read_text()),
    }
    try:
        async with get_sessionmaker()() as session:
            counts = {
                model: int(await session.scalar(select(func.count()).select_from(model)) or 0)
                for model in (Policy, Claim, Grievance)
            }
            expected = {
                Policy: len(seeds["policies"]),
                Claim: len(seeds["claims"]),
                Grievance: len(seeds["grievances"]),
            }
            if all(count == 0 for count in counts.values()):
                await load(**seeds)
            elif counts != expected:
                raise RuntimeError(
                    "Refusing to seed a partially populated reference database: "
                    + ", ".join(
                        f"{model.__tablename__}={counts[model]} (expected {expected[model]})"
                        for model in counts
                    )
                )

            manifest = json.loads((ROOT / "data/corpus/manifest.json").read_text())
            corpus_version = get_settings().CORPUS_VERSION
            if manifest.get("corpus_version") != corpus_version:
                raise RuntimeError("CORPUS_VERSION does not match the bundled synthetic corpus")
            chunks_expected = sum(document["clause_count"] for document in manifest["documents"])
            chunks_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(PolicyChunk)
                    .where(PolicyChunk.corpus_version == corpus_version)
                )
                or 0
            )
            if chunks_count == 0:
                indexed = await index_corpus(session, ROOT / "data/corpus")
                print(f"Indexed {indexed} synthetic policy clauses.")
            elif chunks_count != chunks_expected:
                raise RuntimeError(
                    f"Corpus has {chunks_count} rows; expected {chunks_expected}. "
                    "Review data before changing it."
                )
        print("Render database bootstrap is ready.")
    finally:
        await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
