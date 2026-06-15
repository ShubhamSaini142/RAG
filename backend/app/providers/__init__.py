"""Provider factories. Call these (don't import the OpenAI classes directly)
so the backend stays swappable and easy to fake in tests.
"""
from app.providers.base import EmbeddingProvider, LLMProvider

__all__ = ["EmbeddingProvider", "LLMProvider", "get_embedding_provider", "get_llm_provider"]


def get_embedding_provider() -> EmbeddingProvider:
    from app.providers.openai_provider import OpenAIEmbeddingProvider

    return OpenAIEmbeddingProvider()


def get_llm_provider() -> LLMProvider:
    from app.providers.openai_provider import OpenAILLMProvider

    return OpenAILLMProvider()
