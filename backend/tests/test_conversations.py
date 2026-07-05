"""Conversation history test (chat sessions): list, open (with resolved
citations), isolation, and delete — without a real provider.

Run from backend/ (venv active):  python -m tests.test_conversations
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
            "The Eiffel Tower is in Paris. [1]"
            if "[1]" in user
            else "I don't know based on the provided context."
        )
        for word in answer.split():
            yield word + " "


providers_mod.get_embedding_provider = lambda org_id, db: FakeEmbedder()
providers_mod.get_llm_provider = lambda org_id, db: FakeLLM()

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from app.main import app  # noqa: E402

client = TestClient(app)


def _register() -> tuple[str, str]:
    r = client.post(
        "/auth/register",
        json={"email": f"conv-{uuid.uuid4().hex[:10]}@x.com", "password": "password123"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["org_id"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _seed(org_id: str) -> None:
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


def test_conversations() -> None:
    alice, alice_org = _register()
    _seed(alice_org)

    files = {"file": ("facts.txt", b"The Eiffel Tower is located in Paris, France.", "text/plain")}
    assert client.post("/documents", files=files, headers=_auth(alice)).status_code == 201

    # A chat turn creates a conversation.
    r = client.post("/chat", json={"question": "Where is the Eiffel Tower?"}, headers=_auth(alice))
    assert r.status_code == 200, r.text

    # --- list ---
    convs = client.get("/conversations", headers=_auth(alice))
    assert convs.status_code == 200, convs.text
    items = convs.json()
    assert len(items) == 1, items
    conv_id = items[0]["id"]
    assert items[0]["title"], "conversation should have a title"

    # --- open: user + assistant messages; assistant carries resolved citations ---
    detail = client.get(f"/conversations/{conv_id}", headers=_auth(alice))
    assert detail.status_code == 200, detail.text
    msgs = detail.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"], msgs
    cites = msgs[1]["citations"]
    assert len(cites) >= 1, "assistant answer should have citations"
    assert cites[0]["document"] == "facts.txt", "citation should name the source document"
    assert "score" not in cites[0], "history citations should not expose score"
    assert cites[0]["snippet"], "citation should include a snippet"

    # --- isolation: another org can't see or open it ---
    bob, bob_org = _register()
    _seed(bob_org)
    assert client.get("/conversations", headers=_auth(bob)).json() == []
    assert client.get(f"/conversations/{conv_id}", headers=_auth(bob)).status_code == 404

    # --- delete ---
    assert client.delete(f"/conversations/{conv_id}", headers=_auth(alice)).status_code == 204
    assert client.get("/conversations", headers=_auth(alice)).json() == []
    assert client.get(f"/conversations/{conv_id}", headers=_auth(alice)).status_code == 404

    print("OK - conversations: list -> open (cited, source-named) -> isolation -> delete")


if __name__ == "__main__":
    test_conversations()
