"""OpenAI provider builders (LLM + embeddings). langchain-openai is imported
lazily so the package only loads when an org actually uses OpenAI.
"""
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.langchain_adapters import LangChainEmbeddingProvider, LangChainLLMProvider


def build_llm(model: str, api_key: str, base_url: str | None = None) -> LLMProvider:
    from langchain_openai import ChatOpenAI

    return LangChainLLMProvider(
        ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url or None,
            temperature=0,
            stream_usage=True,  # emit token usage on the final streamed chunk
        )
    )


def build_embedding(model: str, api_key: str, base_url: str | None = None) -> EmbeddingProvider:
    from langchain_openai import OpenAIEmbeddings

    return LangChainEmbeddingProvider(
        OpenAIEmbeddings(model=model, api_key=api_key or "not-needed", base_url=base_url or None)
    )
