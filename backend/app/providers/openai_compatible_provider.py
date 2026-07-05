"""OpenAI-compatible provider builders (Ollama, vLLM, OpenRouter, LM Studio, ...).

Same wire protocol as OpenAI but pointed at a custom `base_url`. The API key may
be a placeholder for local servers that don't require auth.
"""
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.langchain_adapters import LangChainEmbeddingProvider, LangChainLLMProvider


def build_llm(model: str, api_key: str, base_url: str | None = None) -> LLMProvider:
    from langchain_openai import ChatOpenAI

    return LangChainLLMProvider(
        ChatOpenAI(
            model=model,
            api_key=api_key or "not-needed",
            base_url=base_url,
            temperature=0,
            stream_usage=True,  # honored if the server reports usage (some don't)
        )
    )


def build_embedding(model: str, api_key: str, base_url: str | None = None) -> EmbeddingProvider:
    from langchain_openai import OpenAIEmbeddings

    return LangChainEmbeddingProvider(
        OpenAIEmbeddings(model=model, api_key=api_key or "not-needed", base_url=base_url)
    )
