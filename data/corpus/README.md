# Dak synthetic policy corpus, version 1

These are original fictional documents issued in the name of the project's existing **Vantara General Insurance** demo insurer. They are not real contracts, approved products, regulatory summaries or representations of any reference insurer's terms. No real customer data is included. All document pages are visibly labelled as synthetic.

| Code | Authoritative Markdown | Generated PDF | Clauses |
|---|---|---|---|
| ASP | [Health](source/ASP.md) | [Health PDF](pdf/ASP.pdf) | ASP-C01–ASP-C18 |
| MOT | [Private car](source/MOT.md) | [Motor PDF](pdf/MOT.pdf) | MOT-C01–MOT-C18 |
| TRM | [Term life](source/TRM.md) | [Term-life PDF](pdf/TRM.pdf) | TRM-C01–TRM-C18 |

The existing seed product names and insurer identity are preserved. The Markdown explains their mapping to these synthetic documents. Grouping health, motor and life under the same fictional issuer is a demo convention, not a claim about a real insurer's licensing.

## References and original fixture choices

The reference set is recorded in [sources.json](sources.json), with publisher, direct URL, observed document identifier, access date and a short description of its influence. The reference PDFs were consulted online; their contents, branding, UINs and contact details have not been republished as Vantara policy terms.

- [HDFC ERGO Arogya Sanjeevani wording](https://customer-portal-assets.hdfcergo.com/documents/arogya-sanjeevani-policy-retail-pw-570443039657.pdf): topic structure for health benefits, waiting periods, exclusions and evidence.
- [ICICI Lombard Private Car Package wording](https://www.icicilombard.com/docs/default-source/default-document-library/private-car-package-policy-wording.pdf): separation of vehicle damage, third-party liability and optional extensions.
- [HDFC Life Saral Jeevan Bima wording](https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/customer-services/policy-documents-pdf/protection-live/HDFC-Life-Saral-Jeevan-Bima-101N140V02.pdf): protection-only structure, waiting/grace concepts and nomination/evidence topics.

Vantara sentences, scenario procedures, benefit limits and numerical examples are authored test material. For example, the motor deductible, towing allowance and term-life grace durations are deliberately fictional. They must not be attributed to the reference insurers. A few familiar insurance concepts or durations may coincide; that does not establish equivalence or current legal compliance.

## Rebuild and verify

Install the project development dependencies (PDF generation uses `reportlab`; extraction uses the existing runtime dependency `pdfplumber`). From the repository root:

```bash
python -m scripts.build_corpus
python -m scripts.build_corpus --check
pytest tests/test_corpus.py
```

The builder keeps each clause together on one page, then extracts every clause back out of the PDF and compares its full normalised text and title with the Markdown. `manifest.json` records document paths, corpus version, clause counts and SHA-256 checksums. `clauses.json` includes source page numbers for ingestion and review. These JSON exports are build artifacts, not additional SQL schema fields.

Use stable clause IDs as citation targets. Do not renumber surviving clauses when adding content. Any wording change that affects answers must bump the corpus version in source metadata and deployment configuration, regenerate artifacts and invalidate previous semantic-cache matches through version filtering. Archive an earlier corpus before replacing it when historical run replay is required; historical corpus storage is not yet implemented.

[retrieval_probes.json](retrieval_probes.json) contains 15 authored questions and expected clauses. These are inputs for retrieval testing, not evidence that embeddings achieve a particular score or top-k accuracy. They are separate from the planned 200-email labelled evaluation corpus.

## Assessment and provenance boundaries

Customer-specific balances, dates and benefit amounts come from policy tools, never another case or a generic clause. An accident exception conflicting with a deterministic waiting-period result is retained for human review. The wording includes deliberate consumables and historical-event examples for disputed-claim testing.

The current generic eligibility calculator still needs product-specific handling: motor has no illness waiting period, and term-life grace/refund logic requires records the current schema does not contain. The documents make those gaps explicit; they do not certify the existing calculator as a complete policy engine. No claim approval or outgoing email is enabled by generating this corpus.

`app/rag/ingest.py` parses this controlled layout. It does not claim to parse arbitrary insurer PDFs or interpret legal wording. Local CPU embeddings, idempotent indexing, filtered retrieval and guarded semantic-cache functions are implemented; graph integration and validator use remain pending.

## Index and retrieval smoke test

With the local database migrated and required environment variables configured:

```bash
python -m scripts.index_corpus --check-probes
```

The first run downloads the specified MiniLM weights into the gitignored local `.cache/embeddings` directory. The [official model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) documents 384-dimensional embeddings. The loader pins revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` and disables remote model code. A different model revision requires re-indexing under a new corpus version.

The current [measured report](../../docs/retrieval-report.json) records 15/15 expected-clause top-three hits on these authored probes and empty nonsense retrieval. This is a small development smoke set, not a held-out accuracy claim. It also records a real paraphrase cache hit and customer-write guard check using a manually checked fixture; the future validator was not invoked.
