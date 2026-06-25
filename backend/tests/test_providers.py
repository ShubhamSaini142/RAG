"""BYOK settings API + encryption test (no real provider calls).

Patches the provider registry builders with fakes (so the embedding dim-probe
and LLM validation don't hit a real API), then checks:
  - PUT stores config with the API key ENCRYPTED (round-trips in the DB)
  - embedding dimension is auto-detected
  - GET returns MASKED keys and never leaks plaintext

Run from backend/ (venv active):  python -m tests.test_providers
"""
import uuid

from fastapi.testclient import TestClient

import app.providers.registry as registry
from app import crypto
from app.db import SessionLocal
from app.models import ProviderSettings


class FakeEmbedder:
    async def embed_query(self, text):
        return [0.1] * 1536

    async def embed_documents(self, texts):
        return [[0.1] * 1536 for _ in texts]


class FakeLLM:
    async def astream(self, system, user):
        yield "ok"


registry.build_embedding = lambda *a, **k: FakeEmbedder()
registry.build_llm = lambda *a, **k: FakeLLM()

from app.main import app  # noqa: E402

client = TestClient(app)
SECRET_EMBED_KEY = "sk-embed-supersecret-1234"
SECRET_LLM_KEY = "sk-llm-supersecret-9876"


def _register() -> tuple[str, str]:
    r = client.post("/auth/register", json={"email": f"prov-{uuid.uuid4().hex[:10]}@x.com", "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["org_id"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_provider_settings() -> None:
    token, org_id = _register()

    # --- Set embedding provider: dim auto-detected via the (fake) probe ---
    r = client.put(
        "/settings/providers/embedding",
        json={"provider": "openai", "model": "text-embedding-3-small", "api_key": SECRET_EMBED_KEY},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["embedding_dim"] == 1536, r.json()
    assert r.json()["api_key_masked"].endswith("1234")
    assert SECRET_EMBED_KEY not in r.text  # never returns plaintext

    # --- Set LLM provider ---
    r = client.put(
        "/settings/providers/llm",
        json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": SECRET_LLM_KEY},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert SECRET_LLM_KEY not in r.text

    # --- GET returns both, masked, no plaintext ---
    r = client.get("/settings/providers", headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["embedding"]["provider"] == "openai" and body["llm"]["provider"] == "anthropic"
    assert SECRET_EMBED_KEY not in r.text and SECRET_LLM_KEY not in r.text

    # --- Keys are stored ENCRYPTED but decrypt back to the originals ---
    db = SessionLocal()
    try:
        oid = uuid.UUID(org_id)
        emb = db.query(ProviderSettings).filter_by(org_id=oid, kind="embedding").first()
        llm = db.query(ProviderSettings).filter_by(org_id=oid, kind="llm").first()
        assert emb.api_key_encrypted != SECRET_EMBED_KEY  # not plaintext at rest
        assert crypto.decrypt(emb.api_key_encrypted) == SECRET_EMBED_KEY
        assert crypto.decrypt(llm.api_key_encrypted) == SECRET_LLM_KEY
    finally:
        db.close()

    # --- A bad/unsupported provider is rejected ---
    r = client.put(
        "/settings/providers/llm",
        json={"provider": "openai_compatible", "model": "x", "api_key": "k"},
        headers=_auth(token),
    )
    assert r.status_code == 422, r.text  # base_url required for openai_compatible

    print("OK - provider settings: encrypted-at-rest, dim auto-detect, masked GET, validation")


if __name__ == "__main__":
    test_provider_settings()
