"""Analytics test: token usage is recorded on chat and aggregated correctly,
scoped per-user and org-wide, without calling a real provider.

Run from backend/ (venv active):  python -m tests.test_analytics
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
    """Reports token usage like a real streamed LangChain response."""

    def __init__(self) -> None:
        self.last_usage = None

    async def astream(self, system: str, user: str):
        answer = "Based on the context, here is the answer. [1]"
        for word in answer.split():
            yield word + " "
        self.last_usage = {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}


providers_mod.get_embedding_provider = lambda org_id, db: FakeEmbedder()
providers_mod.get_llm_provider = lambda org_id, db: FakeLLM()

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from app.main import app  # noqa: E402

client = TestClient(app)


def _register() -> tuple[str, str]:
    r = client.post(
        "/auth/register",
        json={"email": f"ana-{uuid.uuid4().hex[:10]}@x.com", "password": "password123"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["org_id"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _seed_providers(org_id: str) -> None:
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


def test_analytics() -> None:
    alice, alice_org = _register()
    _seed_providers(alice_org)

    files = {"file": ("facts.txt", b"The Eiffel Tower is in Paris, France.", "text/plain")}
    doc_id = client.post("/documents", files=files, headers=_auth(alice)).json()["id"]
    assert client.get(f"/documents/{doc_id}", headers=_auth(alice)).json()["status"] == "ready"

    # Ask twice -> two usage events, 40 total tokens.
    for _ in range(2):
        r = client.post("/chat", json={"question": "Where is the Eiffel Tower?"}, headers=_auth(alice))
        assert r.status_code == 200, r.text

    # --- Personal analytics ---
    me = client.get("/analytics/me", headers=_auth(alice))
    assert me.status_code == 200, me.text
    data = me.json()
    assert data["scope"] == "me"
    assert data["totals"]["requests"] == 2, data["totals"]
    assert data["totals"]["total_tokens"] == 40, data["totals"]
    assert data["totals"]["input_tokens"] == 24 and data["totals"]["output_tokens"] == 16
    assert data["totals"]["documents"] >= 1
    assert data["totals"]["conversations"] >= 1
    assert any(m["model"] == "fake-llm" for m in data["by_model"])
    assert len(data["daily"]) >= 1

    # --- Org-wide analytics (owner allowed), includes per-user breakdown ---
    org = client.get("/analytics/org", headers=_auth(alice))
    assert org.status_code == 200, org.text
    odata = org.json()
    assert odata["scope"] == "org"
    assert odata["totals"]["total_tokens"] == 40
    assert "by_user" in odata and len(odata["by_user"]) >= 1

    # --- Isolation: a fresh org sees none of Alice's usage ---
    bob, bob_org = _register()
    _seed_providers(bob_org)
    bob_me = client.get("/analytics/me", headers=_auth(bob)).json()
    assert bob_me["totals"]["requests"] == 0 and bob_me["totals"]["total_tokens"] == 0

    print("OK - analytics: token usage recorded, aggregated, scoped per-user + org, isolated")


if __name__ == "__main__":
    test_analytics()
