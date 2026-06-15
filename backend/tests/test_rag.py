"""End-to-end RAG slice test WITHOUT OpenAI.

Swaps the embedding + LLM providers for deterministic fakes (this is exactly
what the provider abstraction is for), runs Celery inline (eager), and exercises
the full pipeline against real Postgres + Qdrant + MinIO:
  register -> upload .txt -> ingest -> /chat (retrieve + stream + cite) -> isolation.

Run from backend/ (venv active):  python -m tests.test_rag
The real OpenAI path is enabled simply by setting OPENAI_API_KEY in .env.
"""
import math
import re
import uuid

from fastapi.testclient import TestClient

import app.providers as providers_mod
from app.celery_app import celery_app
from app.config import settings


# --- Deterministic fakes -----------------------------------------------------
class FakeEmbedder:
    """Bag-of-words hashed into a unit vector — shared tokens => high cosine."""

    def _vec(self, text: str) -> list[float]:
        dim = settings.embedding_dim
        v = [0.0] * dim
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[hash(tok) % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class FakeLLM:
    async def astream(self, system: str, user: str):
        # "[1]" appears in the prompt only when context chunks were retrieved.
        answer = (
            "Based on the provided context, the answer is here. [1]"
            if "[1]" in user
            else "I don't know based on the provided context."
        )
        for word in answer.split():
            yield word + " "


providers_mod.get_embedding_provider = lambda: FakeEmbedder()
providers_mod.get_llm_provider = lambda: FakeLLM()

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

from app.main import app  # noqa: E402  (import after patching providers/celery)

client = TestClient(app)


def _email() -> str:
    return f"rag-{uuid.uuid4().hex[:10]}@example.com"


def _register() -> str:
    r = client.post("/auth/register", json={"email": _email(), "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_rag_slice() -> None:
    alice = _register()

    # --- Upload a .txt document ---
    content = (
        b"The Eiffel Tower is located in Paris, France and was completed in 1889. "
        b"The Great Wall of China is an ancient fortification in northern China."
    )
    r = client.post(
        "/documents",
        files={"file": ("facts.txt", content, "text/plain")},
        headers=_auth(alice),
    )
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]

    # --- Ingestion ran inline (eager) -> document is ready ---
    r = client.get(f"/documents/{doc_id}", headers=_auth(alice))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready", f"ingestion did not succeed: {r.json()}"

    # --- Ask a question -> streamed answer with citations ---
    r = client.post(
        "/chat", json={"question": "Where is the Eiffel Tower located?"}, headers=_auth(alice)
    )
    assert r.status_code == 200, r.text
    body = r.text
    assert "event: citations" in body, body
    assert "event: token" in body, body
    assert "event: done" in body, body
    assert doc_id in body, "citation should reference the uploaded document"

    # --- Isolation: Bob has no documents -> no citations, no grounded answer ---
    bob = _register()
    r = client.post(
        "/chat", json={"question": "Where is the Eiffel Tower located?"}, headers=_auth(bob)
    )
    assert r.status_code == 200, r.text
    assert "data: []" in r.text, "another org's docs must NOT be retrieved"

    # --- Delete removes the document ---
    assert client.delete(f"/documents/{doc_id}", headers=_auth(alice)).status_code == 204
    assert client.get(f"/documents/{doc_id}", headers=_auth(alice)).status_code == 404

    print("OK - RAG slice: upload -> ingest -> retrieve -> cited answer -> isolation -> delete")


if __name__ == "__main__":
    test_rag_slice()
