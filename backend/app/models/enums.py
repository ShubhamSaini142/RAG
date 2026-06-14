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
