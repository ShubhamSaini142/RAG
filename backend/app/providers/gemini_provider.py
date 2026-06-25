"""Google Gemini provider builders (LLM + embeddings)."""
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.langchain_adapters import LangChainEmbeddingProvider, LangChainLLMProvider


def build_llm(model: str, api_key: str, base_url: str | None = None) -> LLMProvider:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return LangChainLLMProvider(
        ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
    )


def build_embedding(model: str, api_key: str, base_url: str | None = None) -> EmbeddingProvider:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return LangChainEmbeddingProvider(
        GoogleGenerativeAIEmbeddings(model=model, google_api_key=api_key)
    )
