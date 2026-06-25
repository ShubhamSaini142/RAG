"""Anthropic (Claude) provider builder — LLM only.

Anthropic has no embeddings API, so this module intentionally exposes only
build_llm; an org using Claude must pick a different embedding provider.
"""
from app.providers.base import LLMProvider
from app.providers.langchain_adapters import LangChainLLMProvider


def build_llm(model: str, api_key: str, base_url: str | None = None) -> LLMProvider:
    from langchain_anthropic import ChatAnthropic

    return LangChainLLMProvider(ChatAnthropic(model=model, api_key=api_key, temperature=0))
