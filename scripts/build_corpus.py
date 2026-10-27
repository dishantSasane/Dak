"""Build deterministic synthetic PDFs, clause export and checksum manifest.

Run `python -m scripts.build_corpus`; use `--check` to verify committed artifacts.
Only original local Markdown is rendered; referenced insurer PDFs are not copied.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
from dataclasses import asdict, replace
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from app.rag.ingest import SourceClause, extract_pdf_clauses, parse_markdown

ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_pdf(path: Path, title: str, document_id: str, clauses: list[SourceClause]) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "CorpusBody",
        parent=styles["BodyText"],
        fontSize=10.5,
        leading=16,
        spaceAfter=10,
        textColor=colors.HexColor("#272727"),
    )
    heading = ParagraphStyle(
        "ClauseHeading",
        parent=styles["Heading2"],
        fontSize=11.5,
        leading=15,
        spaceBefore=10,
        spaceAfter=7,
    )
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(
            "SYNTHETIC DEMO DOCUMENT. Not an insurance contract or an approved "
            "insurance product. All benefits and numerical rules are fictional.",
            body,
        ),
        Paragraph(f"Vantara General Insurance | {document_id} | Wording 1.0 | Corpus 1", body),
        Spacer(1, 12),
    ]
    for clause in clauses:
        story.append(
            KeepTogether(
                [
                    Paragraph(escape(f"{clause.clause_id} | {clause.clause_title}"), heading),
                    Paragraph(escape(clause.content), body),
                ]
            )
        )

    def page_chrome(canvas: Canvas, document: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#606060"))
        canvas.drawString(48, A4[1] - 32, "DAK / VANTARA / SYNTHETIC POLICY CORPUS")
        canvas.drawRightString(A4[0] - 48, A4[1] - 32, document_id)
        canvas.line(48, A4[1] - 44, A4[0] - 48, A4[1] - 44)
        canvas.drawString(48, 28, "FICTIONAL TEST MATERIAL - NOT FOR SALE OR REAL CLAIMS")
        canvas.drawRightString(A4[0] - 48, 28, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=48,
        rightMargin=48,
        topMargin=68,
        bottomMargin=58,
        title=title,
        author="Dak synthetic corpus",
        subject=document_id,
        invariant=1,
    )
    document.build(
        story,
        onFirstPage=page_chrome,
        onLaterPages=page_chrome,
        canvasmaker=Canvas,
    )


async def build(output: Path) -> None:
    metadata = json.loads((ROOT / "sources.json").read_text())
    (output / "pdf").mkdir(parents=True, exist_ok=True)
    manifests: list[dict] = []
    export: list[dict] = []
    for spec in metadata["documents"]:
        code = spec["product_code"]
        source_path = ROOT / spec["source_path"]
        clauses = parse_markdown(source_path.read_text(), code)
        pdf_path = output / spec["pdf_path"]
        render_pdf(pdf_path, spec["title"], spec["document_id"], clauses)
        extracted = await extract_pdf_clauses(pdf_path, code)
        if [replace(clause, page_number=None) for clause in extracted] != clauses:
            raise ValueError(f"{code}: generated PDF does not match its source clauses")
        manifests.append(
            {
                **spec,
                "clause_count": len(clauses),
                "source_sha256": digest(source_path),
                "pdf_sha256": digest(pdf_path),
            }
        )
        export.extend(asdict(clause) for clause in extracted)
    manifest = {
        "corpus_version": metadata["corpus_version"],
        "synthetic": True,
        "wording_version": metadata["wording_version"],
        "sources_sha256": digest(ROOT / "sources.json"),
        "documents": manifests,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "clauses.json").write_text(json.dumps(export, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        asyncio.run(build(ROOT))
        print("Built 3 synthetic PDFs and verified 54 complete clauses against Markdown sources.")
        return
    with tempfile.TemporaryDirectory(prefix="dak-corpus-") as temporary:
        output = Path(temporary)
        asyncio.run(build(output))
        files = ["manifest.json", "clauses.json", "pdf/ASP.pdf", "pdf/MOT.pdf", "pdf/TRM.pdf"]
        for name in files:
            target = ROOT / name
            if not target.exists() or target.read_bytes() != (output / name).read_bytes():
                raise SystemExit(
                    f"Stale corpus artifact: {name}; run python -m scripts.build_corpus"
                )
    print("Corpus PDFs, checksums and clause exports are current and reproducible.")


if __name__ == "__main__":
    main()
