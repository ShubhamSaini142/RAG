"""Structure-aware chunking via LangChain's recursive splitter.

Splits text into overlapping chunks, carrying source metadata through for
citations. Returns a list of {content, metadata, chunk_index}.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def chunk_text(
    text: str,
    metadata: dict | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    if not text or not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    pieces = splitter.split_text(text)
    return [
        {"content": piece, "metadata": dict(metadata or {}), "chunk_index": i}
        for i, piece in enumerate(pieces)
    ]
