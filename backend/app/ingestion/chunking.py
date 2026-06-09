"""Structure-aware chunking.

Splits extracted text into overlapping chunks while respecting structure
(headings, page/sheet boundaries) and carrying source metadata
(page / sheet / url / heading) through for citations.

NOTE: scaffold stub — implemented in the ingestion milestone
(LangChain text splitters under the hood).
"""

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(text: str, metadata: dict | None = None) -> list[dict]:
    raise NotImplementedError("Implemented in the ingestion milestone.")
