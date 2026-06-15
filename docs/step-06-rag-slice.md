# Step 6 — First RAG Slice (ingest → ask)

The payoff step: upload a document, and ask questions answered by an LLM
**grounded in your content, with citations**. This is the end-to-end vertical
slice that wires together the provider, vector-store, ingestion, and RAG layers.

- **Explanation** → understand the pipeline.
- [Setup for collaborators](#setup-for-collaborators) → run it locally (incl. the worker + OpenAI key).
- [Git workflow](#git-workflow--commit--push-to-uat).

---

## What this step delivers

```
        POST /documents (.txt/.md)
                 │  store raw file in MinIO, create Document(status=queued)
                 ▼
        Celery worker  ── extract → chunk → embed → upsert ──►  Qdrant (vectors)
                 │                                    └─────►  Postgres (chunk rows)
                 ▼  Document.status = ready
        POST /chat {question}
                 │  embed query → search Qdrant (org-scoped) → grounded prompt
                 ▼
        SSE stream: citations → answer tokens → done   (answer persisted)
```

Endpoints: `POST/GET/DELETE /documents`, `GET /documents/{id}`, `POST /chat`.

---

## Files

| Area | Files |
|------|-------|
| Providers (swappable AI) | `app/providers/base.py`, `openai_provider.py`, `__init__.py` (factories) |
| Vector store | `app/vectorstore/qdrant_store.py` |
| Object storage | `app/storage.py` |
| Ingestion | `app/ingestion/extractors/`, `chunking.py`, `tasks.py` (Celery) |
| RAG | `app/rag/retriever.py`, `pipeline.py` |
| API | `app/api/documents.py`, `app/api/chat.py` |
| Test (no OpenAI needed) | `tests/test_rag.py` |

---

## Core concepts (the *why* and *how*)

### Provider abstraction (swappable AI)
`get_embedding_provider()` / `get_llm_provider()` return objects implementing our
own interfaces; the OpenAI impls use `langchain-openai`. Nothing else imports
OpenAI directly, so swapping models/providers — or faking them in tests — is a
one-line change. (This is exactly how the test runs with **no API key**.)

### Postgres + Qdrant split
The chunk **text + metadata** live in Postgres (`chunks` table); the **embedding
vector** lives in Qdrant, linked by `qdrant_point_id`. Each store does what it's
best at: relational queries vs. vector similarity search.

### Async ingestion (Celery)
Uploading returns immediately; a **Celery worker** does the slow work
(extract → chunk → embed → store) in the background and flips the document to
`ready` (or `failed` + error). The pipeline is **idempotent**: each run purges
the prior attempt and uses deterministic point ids, so retries self-heal.

### Retrieval + grounded generation
`/chat` embeds the question, searches Qdrant **filtered by `org_id`** (tenant
isolation), builds a grounded prompt ("answer ONLY from context; else say you
don't know"), and **streams** the answer token-by-token over SSE. **Citations**
(which chunks backed the answer) are sent first and stored on the message.

### What's async vs sync
Async where it pays off — **LLM answer streaming** (`astream`). DB/storage/
embeddings are sync; FastAPI runs sync endpoints in a threadpool, and the chat
stream offloads its DB writes via `run_in_threadpool` so the event loop is never
blocked. CPU work (bcrypt, chunking) stays in threads/workers, never on the loop.

---

## Hardening (from the adversarial review)

| Severity | Issue | Fix |
|----------|-------|-----|
| 🟠 High | Non-idempotent ingest left orphan/duplicate vectors on retry | Purge prior attempt + deterministic point ids; vectors-then-commit |
| 🟡 Medium | Sync DB blocked the event loop in the chat stream | Persistence runs via `run_in_threadpool` |
| 🟡 Medium | Client disconnect lost the chat turn | Persist in a `finally` (records partial answer) |
| 🟡 Medium | No upload size cap (OOM risk) | 10 MB cap → HTTP 413 |
| 🔵 Low | Conversation reuse not user-scoped (intra-tenant IDOR) | Require `org_id` **and** `user_id` match |
| 🔵 Low | Empty/whitespace doc marked `ready` | Mark `failed` ("No extractable text content") |
| 🔵 Low | `zip(pieces, vectors)` could silently drop chunks | Length guard + `strict=True` |
| 🔵 Low | `collection_id` not org-validated (defense-in-depth) | Validate ownership → 404 |

> Plus: Celery `task_time_limit`/`acks_late` so a stuck task is killed & redelivered.

---

## Gotcha fixed: use `127.0.0.1`, not `localhost`

Docker publishes ports on **IPv4 only** (`127.0.0.1:PORT`). On Windows,
`localhost` can resolve to IPv6 (`::1`) first, so the **first** DB/service
connection hangs ~130s before falling back to IPv4. All service hosts in `.env`
use `127.0.0.1` to avoid this. Keep it that way.

---

# Setup for collaborators

Prereqs: Steps 0–5 done (infra up, DB migrated, deps installed). Then:

### 1. Add your OpenAI key
```dotenv
# backend/.env
OPENAI_API_KEY=sk-...
```
(Embeddings + the LLM answer need it. The test suite does **not** — it uses fakes.)

### 2. Start infra + run the API and a Celery worker
```powershell
cd backend
docker compose up -d                      # postgres, qdrant, redis, minio
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head                      # if not already applied

# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Celery worker (REQUIRED to process uploads)
celery -A app.celery_app worker --loglevel=info --pool=solo
```
> On Windows use `--pool=solo` (the default prefork pool doesn't work well there).
> Without a running worker, uploaded documents stay stuck at `queued`.

### 3. Try it in Swagger
Open **http://localhost:8000/docs**:
1. `POST /auth/register` → copy the `access_token`.
2. Click **Authorize**, paste the token.
3. `POST /documents` → upload a `.txt`/`.md`.
4. `GET /documents/{id}` → wait for `status: ready`.
5. `POST /chat` → ask a question; watch the streamed, cited answer.

### Run the tests (no OpenAI key needed)
```powershell
python -m tests.test_rag    # upload -> ingest -> retrieve -> cited answer -> isolation -> delete
python -m tests.test_auth   # auth + multi-tenant isolation
```
`test_rag.py` swaps in deterministic fake providers and runs Celery inline
(eager), so it exercises the full pipeline against real Postgres/Qdrant/MinIO
without calling OpenAI.

---

# Git workflow — commit & push to UAT

```powershell
git checkout UAT
git pull origin UAT
git checkout -b feature/<short-description>
git add -A
git status                 # confirm no .env / secrets staged
git commit -m "Step 6: short description"
git push -u origin feature/<short-description>
# then open a PR to UAT, or merge locally and: git push origin UAT
```
Never commit the real `.env`; commit new Alembic migrations when models change.

---

## Known limitations (next phases)
- Only `.txt`/`.md` so far — PDF/OCR, DOCX, Excel, images, websites come next.
- Dense vectors only — hybrid (sparse+dense) search is a later add.
- No conversation memory in the prompt yet; no reranking.
- Uploads read fully into memory (10 MB cap) — stream-to-S3 later.
- No periodic reaper for documents orphaned by a never-run worker.

## Reference
- Auth: [`step-05-auth.md`](step-05-auth.md) · DB: [`step-04-database-schema.md`](step-04-database-schema.md)
- Plan: [`../PLAN.md`](../PLAN.md) · Checklist: [`CHECKLIST.md`](CHECKLIST.md)
