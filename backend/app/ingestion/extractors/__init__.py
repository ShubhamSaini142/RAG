"""Per-source-type text extractors.

One extractor module per source_type (added in the ingestion milestone):
  pdf.py      - text layer + OCR fallback for scanned pages
  docx.py     - headings/tables preserved
  excel.py    - per-sheet, table-aware (xlsx/csv)
  text.py     - txt / markdown, direct
  image.py    - OCR (+ optional vision caption later)
  website.py  - fetch + clean-text (single URL now, crawl later)

Each exposes: extract(source) -> list[dict]  (text + source metadata)
A registry maps source_type -> extractor.
"""
