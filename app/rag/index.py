"""Checksum-verified, atomic replacement of one synthetic corpus version."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import PolicyChunk
from app.rag.embeddings import Embedder, embed_texts, validate_embeddings
from app.rag.ingest import SourceClause, extract_pdf_clauses, parse_markdown


def _read_metadata(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text())


def _checked_source(root: Path, spec: dict) -> list[SourceClause]:
    for kind in ["source", "pdf"]:
        path = root / spec[f"{kind}_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec[f"{kind}_sha256"]:
            raise ValueError(f"{spec['product_code']}: {kind} checksum mismatch; rebuild corpus")
    return parse_markdown((root / spec["source_path"]).read_text(), spec["product_code"])


async def index_corpus(
    session: AsyncSession,
    root: Path,
    *,
    embed: Embedder = embed_texts,
) -> int:
    manifest = await asyncio.to_thread(_read_metadata, root)
    version = get_settings().CORPUS_VERSION
    if manifest.get("synthetic") is not True or manifest["corpus_version"] != version:
        raise ValueError("Synthetic manifest and configured CORPUS_VERSION must agree")
    metadata_hash = await asyncio.to_thread(
        lambda: hashlib.sha256((root / "sources.json").read_bytes()).hexdigest()
    )
    if metadata_hash != manifest["sources_sha256"]:
        raise ValueError("Reference metadata checksum mismatch; rebuild corpus")
    clauses: list[SourceClause] = []
    for spec in manifest["documents"]:
        source = await asyncio.to_thread(_checked_source, root, spec)
        extracted = await extract_pdf_clauses(root / spec["pdf_path"], spec["product_code"])
        if source != [replace(clause, page_number=None) for clause in extracted]:
            raise ValueError("Extracted PDF content differs from its original source")
        if len(extracted) != spec["clause_count"]:
            raise ValueError("Manifest clause count differs from extracted PDF")
        clauses.extend(extracted)
    keys = {(clause.product_code, clause.clause_id) for clause in clauses}
    if len(keys) != len(clauses) or not clauses:
        raise ValueError("Corpus must have unique, nonempty clause targets")
    vectors = await embed([f"{clause.clause_title}. {clause.content}" for clause in clauses])
    validate_embeddings(vectors, len(clauses))
    try:
        # PostgreSQL advisory lock serializes re-ingestion of this corpus version.
        from sqlalchemy import text

        await session.execute(
            text("SELECT pg_advisory_xact_lock(44201, :version)"), {"version": version}
        )
        products = sorted({clause.product_code for clause in clauses})
        await session.execute(
            delete(PolicyChunk).where(
                PolicyChunk.corpus_version == version, PolicyChunk.product_code.in_(products)
            )
        )
        session.add_all(
            [
                PolicyChunk(
                    product_code=clause.product_code,
                    clause_id=clause.clause_id,
                    clause_title=clause.clause_title,
                    content=clause.content,
                    page_number=clause.page_number,
                    corpus_version=version,
                    embedding=vector,
                )
                for clause, vector in zip(clauses, vectors, strict=True)
            ]
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return len(clauses)
