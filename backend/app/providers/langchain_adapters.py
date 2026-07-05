"""Thin adapters wrapping any LangChain chat model / embeddings as our
provider interfaces. All LangChain chat models expose the same async
`astream`, and all embeddings expose `aembed_*`, so one adapter each covers
every provider.
"""
from collections.abc import AsyncIterator

from app.providers.base import EmbeddingProvider, LLMProvider


class LangChainLLMProvider(LLMProvider):
    def __init__(self, chat_model) -> None:
        self._llm = chat_model
        # Populated after astream completes with the provider's token usage
        # ({"input_tokens", "output_tokens", "total_tokens"}) when available.
        self.last_usage: dict | None = None

    async def astream(self, system: str, user: str) -> AsyncIterator[str]:
        # Accumulate chunks so we can read usage_metadata off the aggregate,
        # which is how LangChain surfaces token counts for streamed responses.
        full = None
        self.last_usage = None
        try:
            async for chunk in self._llm.astream([("system", system), ("human", user)]):
                full = chunk if full is None else full + chunk
                text = chunk.content
                if text:
                    yield text if isinstance(text, str) else str(text)
        finally:
            if full is not None:
                self.last_usage = getattr(full, "usage_metadata", None)


class LangChainEmbeddingProvider(EmbeddingProvider):
    def __init__(self, embeddings) -> None:
        self._emb = embeddings

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._emb.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        return await self._emb.aembed_query(text)
