"""OpenAI implementation of the provider interfaces (via langchain-openai)."""
from collections.abc import AsyncIterator

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings
from app.providers.base import EmbeddingProvider, LLMProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._emb = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._emb.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._emb.embed_query(text)


class OpenAILLMProvider(LLMProvider):
    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )

    async def astream(self, system: str, user: str) -> AsyncIterator[str]:
        async for chunk in self._llm.astream([("system", system), ("human", user)]):
            text = chunk.content
            if text:
                yield text if isinstance(text, str) else str(text)
