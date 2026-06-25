"""End-to-end RAG slice test WITHOUT real OpenAI (BYOK-aware).

Swaps the (now org-aware) embedding + LLM factories for deterministic fakes,
seeds per-org provider config in the DB, runs Celery inline (eager), and
exercises the full pipeline against real Postgres + Qdrant + MinIO:
  register -> require-key gate -> configure -> upload -> ingest -> /chat -> isolation.

Run from backend/ (venv active):  python -m tests.test_rag
"""
import math
import re
import uuid

from fastapi.testclient import TestClient

import app.providers as providers_mod
from app import crypto
from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.models import ProviderSettings


class FakeEmbedder:
    def _vec(self, text: str) -> list[float]:
        dim = settings.embedding_dim
        v = [0.0] * dim
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[hash(tok) % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    async def embed_query(self, text):
        return self._vec(text)


class FakeLLM:
    async def astream(self, system: str, user: str):
        answer = (
            "Based on the provided context, the answer is here. [1]"
            if "[1]" in user
            else "I don't know based on the provided context."
        )
        for word in answer.split():
            yield word + " "


# Org-aware factories now take (org_id, db); fakes ignore both.
providers_mod.get_embedding_provider = lambda org_id, db: FakeEmbedder()
providers_mod.get_llm_provider = lambda org_id, db: FakeLLM()

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from app.main import app  # noqa: E402

client = TestClient(app)


def _register() -> tuple[str, str]:
    r = client.post("/auth/register", json={"email": f"rag-{uuid.uuid4().hex[:10]}@x.com", "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["org_id"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _seed_providers(org_id: str) -> None:
    """Seed per-org provider config (gating + embedding_dim read these)."""
    db = SessionLocal()
    try:
        oid = uuid.UUID(org_id)
        db.add(ProviderSettings(org_id=oid, kind="embedding", provider="openai",
                                model="fake-embed", api_key_encrypted=crypto.encrypt("sk-test"),
                                embedding_dim=settings.embedding_dim))
        db.add(ProviderSettings(org_id=oid, kind="llm", provider="openai",
                                model="fake-llm", api_key_encrypted=crypto.encrypt("sk-test")))
        db.commit()
    finally:
        db.close()


def test_rag_slice() -> None:
    alice, alice_org = _register()
    content = (
        b"The Eiffel Tower is located in Paris, France and was completed in 1889. "
        b"The Great Wall of China is an ancient fortification in northern China."
    )
    files = {"file": ("facts.txt", content, "text/plain")}

    # --- Require-key: uploading before configuring a provider is rejected ---
    assert client.post("/documents", files=files, headers=_auth(alice)).status_code == 409

    # --- Configure providers (seeded directly) -> upload now works ---
    _seed_providers(alice_org)
    r = client.post("/documents", files=files, headers=_auth(alice))
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    # --- Ingestion ran inline (eager) into the org's own collection -> ready ---
    r = client.get(f"/documents/{doc_id}", headers=_auth(alice))
    assert r.status_code == 200 and r.json()["status"] == "ready", r.text

    # --- Ask a question -> streamed answer with citations ---
    r = client.post("/chat", json={"question": "Where is the Eiffel Tower located?"}, headers=_auth(alice))
    assert r.status_code == 200, r.text
    assert "event: citations" in r.text and "event: token" in r.text and "event: done" in r.text
    assert doc_id in r.text

    # --- Isolation: Bob's own org/collection has no docs -> no citations ---
    bob, bob_org = _register()
    _seed_providers(bob_org)
    r = client.post("/chat", json={"question": "Where is the Eiffel Tower located?"}, headers=_auth(bob))
    assert r.status_code == 200 and "data: []" in r.text, "another org's docs must NOT be retrieved"

    # --- Delete removes the document ---
    assert client.delete(f"/documents/{doc_id}", headers=_auth(alice)).status_code == 204
    assert client.get(f"/documents/{doc_id}", headers=_auth(alice)).status_code == 404

    print("OK - RAG slice (BYOK): gate -> configure -> upload -> ingest -> cited answer -> isolation -> delete")


if __name__ == "__main__":
    test_rag_slice()
