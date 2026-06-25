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

    async def astream(self, system: str, user: str) -> AsyncIterator[str]:
        async for chunk in self._llm.astream([("system", system), ("human", user)]):
            text = chunk.content
            if text:
                yield text if isinstance(text, str) else str(text)


class LangChainEmbeddingProvider(EmbeddingProvider):
    def __init__(self, embeddings) -> None:
        self._emb = embeddings

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._emb.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        return await self._emb.aembed_query(text)
