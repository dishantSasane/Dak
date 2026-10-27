"""Synthetic wording sources and generated PDFs must preserve citation targets."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.rag.ingest import extract_pdf_clauses, parse_markdown

ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus"


@pytest.mark.parametrize("code", ["ASP", "MOT", "TRM"])
def test_authoritative_source_has_unique_complete_clauses(code: str) -> None:
    source = (ROOT / "source" / f"{code}.md").read_text()
    clauses = parse_markdown(source, code)
    assert len(clauses) == 18
    assert [clause.clause_id for clause in clauses] == [f"{code}-C{n:02}" for n in range(1, 19)]
    assert all(clause.content and clause.clause_title for clause in clauses)
    assert "SYNTHETIC DEMO DOCUMENT" in source


@pytest.mark.parametrize("code", ["ASP", "MOT", "TRM"])
async def test_pdf_roundtrip_preserves_every_clause(code: str) -> None:
    source = parse_markdown((ROOT / "source" / f"{code}.md").read_text(), code)
    extracted = await extract_pdf_clauses(ROOT / "pdf" / f"{code}.pdf", code)
    assert len(extracted) == len(source)
    for expected, actual in zip(source, extracted, strict=True):
        assert actual.page_number is not None and actual.page_number > 0
        assert replace(actual, page_number=None) == expected


@pytest.mark.parametrize(
    "source",
    [
        "# missing clauses",
        "## ASP-C01 | Empty",
        "## ASP-C01 | One\nFirst.\n## ASP-C01 | Again\nSecond.",
        "## MOT-C01 | Wrong product\nText.",
        "## ASP-C01 | One\nText.\n## missing identifier\nLost text.",
    ],
)
def test_invalid_or_ambiguous_clause_sources_fail(source: str) -> None:
    with pytest.raises(ValueError):
        parse_markdown(source, "ASP")


def test_reference_and_document_metadata_are_explicit() -> None:
    metadata = json.loads((ROOT / "sources.json").read_text())
    assert metadata["synthetic"] is True
    assert metadata["corpus_version"] == 1
    references = {row["id"]: row for row in metadata["references"]}
    for document in metadata["documents"]:
        assert document["reference_ids"]
        for identifier in document["reference_ids"]:
            reference = references[identifier]
            assert reference["url"].startswith("https://")
            assert reference["observed_document_identifier"]


async def test_pdf_product_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError):
        await extract_pdf_clauses(ROOT / "pdf" / "ASP.pdf", "MOT")


def test_manifest_hashes_and_probe_citations_match_sources() -> None:
    import hashlib

    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert (
        manifest["sources_sha256"]
        == hashlib.sha256((ROOT / "sources.json").read_bytes()).hexdigest()
    )
    identifiers = set()
    for document in manifest["documents"]:
        for kind in ["source", "pdf"]:
            assert (
                document[f"{kind}_sha256"]
                == hashlib.sha256((ROOT / document[f"{kind}_path"]).read_bytes()).hexdigest()
            )
        clauses = parse_markdown(
            (ROOT / document["source_path"]).read_text(), document["product_code"]
        )
        assert document["clause_count"] == len(clauses)
        identifiers.update(clause.clause_id for clause in clauses)
    probes = json.loads((ROOT / "retrieval_probes.json").read_text())
    assert probes["corpus_version"] == manifest["corpus_version"]
    assert len(probes["probes"]) >= 10
    for probe in probes["probes"]:
        assert probe["expected_clause_ids"]
        for identifier in probe["expected_clause_ids"]:
            assert identifier in identifiers
            assert identifier.startswith(probe["product_code"] + "-")


def test_pdf_pages_keep_clauses_whole_and_use_stable_metadata() -> None:
    import pdfplumber

    exported = json.loads((ROOT / "clauses.json").read_text())
    for code in ["ASP", "MOT", "TRM"]:
        with pdfplumber.open(ROOT / "pdf" / f"{code}.pdf") as document:
            assert document.metadata["CreationDate"].startswith("D:20000101000000")
            pages = [" ".join((page.extract_text() or "").split()) for page in document.pages]
            assert all("FICTIONAL TEST MATERIAL" in page for page in pages)
            for clause in exported:
                if clause["product_code"] == code:
                    assert clause["content"] in pages[clause["page_number"] - 1]
