"""OpenAI implementation of the provider interfaces (via langchain-openai).

NOTE: scaffold stub — full implementation lands in the RAG-query milestone.
"""
from collections.abc import AsyncIterator

from app.config import settings
from app.providers.base import EmbeddingProvider, LLMProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.model = settings.embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Implemented in the ingestion milestone.")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("Implemented in the RAG-query milestone.")


class OpenAILLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.model = settings.llm_model

    async def stream(self, prompt: str, context: list[str]) -> AsyncIterator[str]:
        raise NotImplementedError("Implemented in the RAG-query milestone.")
        yield  # pragma: no cover  (marks this as an async generator)
