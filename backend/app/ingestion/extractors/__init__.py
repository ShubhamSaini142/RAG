"""Per-source-type text extractors.

A registry maps source_type -> extractor function. Each extractor takes raw
bytes and returns a list of {text, metadata} segments. More types
(pdf, docx, excel, image, website) are added in the widen-coverage phase.
"""
from app.ingestion.extractors import text as _text

_REGISTRY = {
    "txt": _text.extract,
    "md": _text.extract,
}


def extract(source_type: str, raw: bytes) -> list[dict]:
    fn = _REGISTRY.get(source_type)
    if fn is None:
        raise ValueError(f"No extractor registered for source_type '{source_type}'")
    return fn(raw)
