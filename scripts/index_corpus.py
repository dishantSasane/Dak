"""Index the synthetic PDFs with real local MiniLM embeddings; optionally measure probes."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from app.cache.semantic import lookup_answer, write_answer
from app.config import get_settings
from app.db.session import get_engine, get_sessionmaker
from app.models.schemas import Draft, DraftSentence, ValidationResult
from app.rag.embeddings import MODEL_NAME, MODEL_REVISION
from app.rag.index import index_corpus
from app.rag.retrieve import search_policy_docs

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"


async def run(check_probes: bool) -> None:
    try:
        async with get_sessionmaker()() as session:
            count = await index_corpus(session, CORPUS)
            print(f"Indexed {count} clauses with {MODEL_NAME} at revision {MODEL_REVISION}.")
            if not check_probes:
                return
            fixtures = json.loads((CORPUS / "retrieval_probes.json").read_text())
            results = []
            for probe in fixtures["probes"]:
                chunks = await search_policy_docs(
                    session, probe["question"], probe["product_code"], use_cache=False
                )
                top_three = {chunk.clause_id for chunk in chunks[:3]}
                results.append(
                    {
                        **probe,
                        "top_3_hit": bool(top_three.intersection(probe["expected_clause_ids"])),
                        "retrieved": [chunk.model_dump() for chunk in chunks],
                    }
                )
            nonsense = await search_policy_docs(
                session, "zxqv blorpt zzzzz quuxq", "MOT", use_cache=False
            )
            # This fixture sentence is manually checked against ASP-C07. It is
            # not evidence that the still-unimplemented validator has run.
            generic_question = "Please tell me the initial waiting period"
            generic_chunks = await search_policy_docs(
                session, generic_question, "ASP", use_cache=False
            )
            fixture = Draft(
                sentences=[
                    DraftSentence(
                        text="The default initial waiting period for illness is 30 days.",
                        kind="factual",
                        cite="ASP-C07",
                    )
                ]
            )
            stored = await write_answer(
                session,
                generic_question,
                "ASP",
                fixture,
                ValidationResult(passed=True),
                generic_chunks,
                used_customer_tools=False,
                numbers_from_policy_record=False,
            )
            cache_hit = await lookup_answer(session, "Tell me the initial waiting period", "ASP")
            customer_stored = await write_answer(
                session,
                generic_question,
                "ASP",
                fixture,
                ValidationResult(passed=True),
                generic_chunks,
                used_customer_tools=True,
                numbers_from_policy_record=False,
            )
            report = {
                "measured_at": datetime.now(UTC).isoformat(),
                "kind": "authored retrieval smoke probes, not held-out email evaluation",
                "model": MODEL_NAME,
                "model_revision": MODEL_REVISION,
                "sentence_transformers_version": version("sentence-transformers"),
                "torch_version": version("torch"),
                "corpus_version": get_settings().CORPUS_VERSION,
                "score_floor": get_settings().RETRIEVAL_SCORE_FLOOR,
                "cache_smoke": {
                    "fixture_validation": "manual source check; deterministic validator pending",
                    "generic_fixture_stored": stored,
                    "paraphrase_hit": cache_hit is not None,
                    "customer_specific_write_blocked": not customer_stored,
                    "semantic_threshold": get_settings().SEMANTIC_CACHE_THRESHOLD,
                },
                "probe_count": len(results),
                "top_3_hits": sum(row["top_3_hit"] for row in results),
                "nonsense_returns_empty": not nonsense,
                "results": results,
            }
            target = ROOT / "docs" / "retrieval-report.json"
            target.write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"Top-3 expected-clause hits: {report['top_3_hits']}/{len(results)}; "
                f"nonsense empty: {not nonsense}. Report: {target.relative_to(ROOT)}"
            )
    finally:
        await get_engine().dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-probes", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.check_probes))


if __name__ == "__main__":
    main()
