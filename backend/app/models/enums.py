"""String enums used across models. Stored as plain strings in the DB
(flexible to extend without enum-altering migrations); used as constants
in code for safety.
"""
from enum import Enum


class Role(str, Enum):
    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class SourceType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    xlsx = "xlsx"
    xls = "xls"
    csv = "csv"
    txt = "txt"
    image = "image"
    website = "website"


class DocumentStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class FeedbackRating(str, Enum):
    up = "up"
    down = "down"


class ProviderKind(str, Enum):
    llm = "llm"
    embedding = "embedding"


class LLMProviderName(str, Enum):
    openai = "openai"
    anthropic = "anthropic"
    gemini = "gemini"
    openai_compatible = "openai_compatible"


class EmbeddingProviderName(str, Enum):
    # Note: Anthropic has no embeddings API — it's LLM-only.
    openai = "openai"
    gemini = "gemini"
    openai_compatible = "openai_compatible"
