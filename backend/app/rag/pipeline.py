"""RAG generation: build a grounded prompt from retrieved chunks and stream
the LLM answer. Citations are derived from the same chunks by the caller.
"""
from collections.abc import AsyncIterator

from app import providers
from app.vectorstore.base import SearchHit

GROUNDED_SYSTEM = (
    "You are a helpful assistant answering questions about the user's documents. "
    "Answer using ONLY the provided context. If the answer is not contained in the "
    "context, say you don't know — do not make anything up. Be concise and refer to "
    "sources by their number like [1], [2] where relevant."
)


def build_user_prompt(question: str, hits: list[SearchHit]) -> str:
    if hits:
        context = "\n\n".join(f"[{i + 1}] {h.content}" for i, h in enumerate(hits))
    else:
        context = "(no relevant context found)"
    return f"Context:\n{context}\n\nQuestion: {question}"


async def stream_answer(question: str, hits: list[SearchHit]) -> AsyncIterator[str]:
    llm = providers.get_llm_provider()
    user_prompt = build_user_prompt(question, hits)
    async for delta in llm.astream(GROUNDED_SYSTEM, user_prompt):
        yield delta
