"""Clause boundaries for Dak's controlled synthetic Markdown and PDF corpus.

This is deliberately not a general parser for arbitrary insurer layouts. The
original Markdown is authoritative; generated PDF text must roundtrip exactly.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

PRODUCTS = frozenset({"ASP", "MOT", "TRM"})
HEADING = re.compile(r"^(?P<id>[A-Z]{3}-C[0-9]{2})\s+\|\s+(?P<title>.+)$")


@dataclass(frozen=True)
class SourceClause:
    product_code: str
    clause_id: str
    clause_title: str
    content: str
    page_number: int | None = None


def _parse_pages(pages: list[str], product_code: str, *, markdown: bool) -> list[SourceClause]:
    if product_code not in PRODUCTS:
        raise ValueError(f"Unknown product code: {product_code}")
    clauses: list[SourceClause] = []
    seen: set[str] = set()
    identifier = title = ""
    content: list[str] = []
    start_page: int | None = None

    def finish() -> None:
        if not identifier:
            return
        text = " ".join(" ".join(content).split())
        if not text:
            raise ValueError(f"Empty clause: {identifier}")
        clauses.append(SourceClause(product_code, identifier, title, text, start_page))

    for page_number, page in enumerate(pages, start=1):
        for raw_line in page.splitlines():
            line = raw_line.strip()
            if markdown and line.startswith("## "):
                line = line[3:]
                if HEADING.fullmatch(line) is None:
                    raise ValueError(f"Malformed clause heading: {line}")
            elif markdown and line.startswith("#"):
                if identifier:
                    raise ValueError(f"Unexpected heading inside a clause: {line}")
                continue
            match = HEADING.fullmatch(line)
            if match:
                finish()
                identifier = match["id"]
                if not identifier.startswith(f"{product_code}-"):
                    raise ValueError(f"Clause {identifier} is not for product {product_code}")
                if identifier in seen:
                    raise ValueError(f"Duplicate clause ID: {identifier}")
                seen.add(identifier)
                title = match["title"]
                content = []
                start_page = None if markdown else page_number
            elif identifier and line:
                content.append(line)
    finish()
    if not clauses:
        raise ValueError("Document has no recognised clauses")
    return clauses


def parse_markdown(text: str, product_code: str) -> list[SourceClause]:
    return _parse_pages([text], product_code, markdown=True)


def _extract_pdf(path: Path, product_code: str) -> list[SourceClause]:
    import pdfplumber

    with pdfplumber.open(path) as document:
        # The controlled renderer keeps page headers/footers outside this region.
        pages = [
            page.crop((0, 60, page.width, page.height - 48)).extract_text() or ""
            for page in document.pages
        ]
    return _parse_pages(pages, product_code, markdown=False)


async def extract_pdf_clauses(path: Path, product_code: str) -> list[SourceClause]:
    """Extract complete clauses without blocking the event loop on PDF I/O."""
    return await asyncio.to_thread(_extract_pdf, path, product_code)
