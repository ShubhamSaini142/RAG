"""RAG generation pipeline (LangChain LCEL).

retrieve -> build grounded prompt ("answer only from context; else say you
don't know") -> stream answer from LLMProvider -> attach citations.

NOTE: scaffold stub — implemented in the RAG-query milestone.
"""
from collections.abc import AsyncIterator


async def answer(
    org_id: str, question: str, collection_id: str | None = None,
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    """Stream a grounded, cited answer for a tenant's question."""
    raise NotImplementedError("Implemented in the RAG-query milestone.")
    yield  # pragma: no cover  (marks this as an async generator)
