"""Provider abstraction so the LLM / embedding backend is swappable.

OpenAI is the first implementation; any provider can be added by implementing
these interfaces and wiring it via the factories in app.providers.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one dense embedding vector per input text."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Return the dense embedding vector for a query string."""


class LLMProvider(ABC):
    @abstractmethod
    def astream(self, system: str, user: str) -> AsyncIterator[str]:
        """Yield answer text deltas given a system prompt and a user message."""
