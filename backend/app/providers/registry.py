"""Provider redirector: maps a provider name to the right provider module's
builder. Each provider lives in its own module (openai_provider, anthropic_provider,
gemini_provider, openai_compatible_provider). Add a provider = add a module + a
row in the maps below; nothing else changes.
"""
from app.models.enums import EmbeddingProviderName, LLMProviderName
from app.providers import (
    anthropic_provider,
    gemini_provider,
    openai_compatible_provider,
    openai_provider,
)
from app.providers.base import EmbeddingProvider, LLMProvider

# provider name -> builder(model, api_key, base_url) -> Provider
_LLM_BUILDERS = {
    LLMProviderName.openai.value: openai_provider.build_llm,
    LLMProviderName.openai_compatible.value: openai_compatible_provider.build_llm,
    LLMProviderName.anthropic.value: anthropic_provider.build_llm,
    LLMProviderName.gemini.value: gemini_provider.build_llm,
}

# Note: Anthropic has no embeddings, so it is intentionally absent here.
_EMBEDDING_BUILDERS = {
    EmbeddingProviderName.openai.value: openai_provider.build_embedding,
    EmbeddingProviderName.openai_compatible.value: openai_compatible_provider.build_embedding,
    EmbeddingProviderName.gemini.value: gemini_provider.build_embedding,
}


def build_llm(
    provider: str, model: str, api_key: str, base_url: str | None = None
) -> LLMProvider:
    builder = _LLM_BUILDERS.get(provider)
    if builder is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return builder(model, api_key, base_url)


def build_embedding(
    provider: str, model: str, api_key: str, base_url: str | None = None
) -> EmbeddingProvider:
    builder = _EMBEDDING_BUILDERS.get(provider)
    if builder is None:
        raise ValueError(f"Unsupported embedding provider: {provider}")
    return builder(model, api_key, base_url)
