"""Symmetric encryption for provider API keys stored at rest.

Uses Fernet (AES-128-CBC + HMAC) with the app-level ENCRYPTION_KEY. Provider
keys are encrypted before they touch the database and decrypted only when a
request actually needs to call the provider. They are never logged or returned
in plaintext (see `mask`).
"""
from functools import lru_cache

from cryptography.fernet import Fernet

from app.config import settings


@lru_cache
def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def mask(plaintext: str) -> str:
    """Return a display-safe hint. Only reveals the last 4 chars for keys long
    enough that those 4 chars are a small fraction (real provider keys are long);
    short secrets are fully hidden.
    """
    if not plaintext:
        return ""
    if len(plaintext) < 12:
        return "••••••••"
    return "••••" + plaintext[-4:]
