# Plan: RAG Knowledge-Base SaaS — Phase 1 Build

> Living document. We'll keep updating this as the build evolves.

## Context

We're building a multi-tenant **Retrieval-Augmented Generation (RAG)** knowledge-base SaaS from scratch. Users in an organization upload/connect content (PDF, DOC/DOCX, Excel/CSV, text, images, websites), the system extracts → chunks → embeds → stores the content, and users ask natural-language questions that are answered by an LLM grounded in their own documents, **with citations**.

Decisions locked in with the user:
- **Stack:** Python (FastAPI) backend + Next.js frontend
- **Tenancy:** multi-tenant from day 1 (org-based isolation everywhere)
- **Hosting:** undecided → build **container-first** (docker-compose locally, portable to any cloud)
- **AI:** OpenAI for generation + embeddings initially, but behind a **provider-abstraction layer** so any model/provider can be swapped without touching app logic
- **Vector store:** **Qdrant from day 1** (native payload filtering for multi-tenancy + native hybrid search)
- **Orchestration:** **LangChain ecosystem** (loaders, splitters, retrievers, LCEL) — not LlamaIndex

Goal of this phase: a working, deployable, multi-tenant RAG app covering the full ingest→ask loop for the required source types, with the scalability boundaries (async ingestion, stateless API, swappable AI, namespaced vectors) baked in so growth is a config change, not a rewrite.

---

## Architecture (container-first)

```
                ┌─────────────┐
   Browser ───► │  Next.js    │  (auth UI, upload, chat, doc mgmt)
                └──────┬──────┘
                       │ REST/SSE
                ┌──────▼──────────────┐
                │  FastAPI API        │  stateless, horizontally scalable
                │  (auth, RAG query,  │
                │   upload, mgmt)     │
                └───┬───────────┬─────┘
        enqueue job │           │ query
                ┌───▼────┐  ┌───▼──────────────┐
                │ Redis  │  │ LangChain RAG    │──► OpenAI (swappable)
                │ queue  │  │ (provider abstr.)│
                └───┬────┘  └──────────────────┘
          ┌─────────▼─────────┐
          │ Celery workers    │  extract→chunk→embed (async)
          └──┬─────────┬──────┘
             │         │
     ┌───────▼──┐  ┌───▼────────────┐  ┌──────────────┐
     │ Postgres │  │ Object storage │  │   Qdrant     │
     │ metadata │  │ (S3/MinIO)     │  │ vectors +    │
     │  only    │  │ raw files      │  │ payload      │
     └──────────┘  └────────────────┘  └──────────────┘
```

### Components & roles
- **FastAPI API** — stateless; auth, tenant resolution, upload intake, document management, RAG query (SSE streaming). Scales horizontally behind a load balancer.
- **Celery + Redis** — async ingestion jobs (the key scalability decision: ingestion is fully decoupled from serving).
- **Postgres** — relational metadata only (orgs, users, documents, chunk records, conversations). No vectors here.
- **Qdrant** — vector store from day 1. Stores dense (+ sparse for hybrid) vectors with payload (`org_id`, `document_id`, `chunk_id`, content, metadata). Native payload filtering gives clean per-tenant isolation; native sparse+dense hybrid search.
- **Object storage** — MinIO locally (S3-compatible), real S3/R2 in cloud. Raw files never live in the DB.
- **Provider abstraction** — `LLMProvider` + `EmbeddingProvider` interfaces; OpenAI is the first impl. Swapping providers = new class + config, no app changes.
- **LangChain** — document loaders, text splitters, retrievers, and LCEL chains for the RAG pipeline. Kept behind our own thin service layer so LangChain stays a library, not a framework lock-in.

### Tech choices
| Concern | Choice | Why |
|---------|--------|-----|
| Backend | FastAPI (Python 3.11+) | Best RAG/ML ecosystem; async-native |
| Frontend | Next.js (App Router) + Tailwind | Standard, SSR, good DX |
| Queue | Celery + Redis | Mature async task processing |
| Metadata DB | Postgres | Relational + multi-tenant (metadata only) |
| Vector store | **Qdrant (from day 1)** | Payload filtering for tenancy + native hybrid search |
| File storage | MinIO → S3/R2 | S3-compatible, portable |
| Extraction | LangChain loaders + `unstructured`/Tika | Handles all required formats |
| OCR | Tesseract (+ optional cloud OCR) | Scanned PDFs & images |
| Web crawl | LangChain web loaders + `trafilatura` / Playwright | Clean text extraction; JS sites later |
| RAG orchestration | **LangChain** (loaders, splitters, retrievers, LCEL) behind thin service layer | Rich ecosystem; avoid framework lock-in |
| Auth | JWT + org/role model | Multi-tenant from day 1 |
| Migrations | Alembic | Schema versioning |
| Packaging | docker-compose | Container-first, deploy anywhere |

---

## Data Model (Postgres, multi-tenant)

`tenant_id` (org) is on **every** Postgres table; all queries filter by it. Use Postgres **Row-Level Security (RLS)** as a safety net.

**Postgres (metadata):**
- **organizations** — id, name, plan, created_at
- **users** — id, email, hashed_password, name
- **memberships** — user_id, org_id, role (owner/admin/editor/viewer) — users belong to one or more orgs
- **collections** — id, org_id, name, description (group documents into knowledge bases)
- **documents** — id, org_id, collection_id, source_type (pdf/docx/xlsx/csv/txt/image/website), filename/url, storage_key, content_hash (dedup), status (queued/processing/ready/failed), error_msg, page/sheet metadata, created_by, timestamps
- **chunks** — id, org_id, document_id, content (text), metadata jsonb (page/sheet/url/heading), chunk_index, qdrant_point_id. (Vector lives in Qdrant; this row is the system-of-record for management/joins.)
- **conversations** / **messages** — id, org_id, user_id, role, content, cited_chunk_ids[] (chat history + memory)
- **feedback** — message_id, org_id, rating (up/down), comment

**Qdrant (vectors):**
- One collection (e.g. `kb_chunks`) with dense vectors (1536-dim) + sparse vectors for hybrid.
- Point id = `chunk.qdrant_point_id`; payload = `{ org_id, collection_id, document_id, chunk_id, content, source metadata }`.
- **Tenant isolation:** every search includes a payload filter `org_id == <tenant>` (+ optional `collection_id`). Indexed payload fields for fast filtering. (Per-tenant collections remain an option at higher scale.)

---

## Ingestion Pipeline (async, one extractor per source type)

API receives upload/URL → validates (type, size) → stores raw file to object storage → creates `document` row (status=queued) → enqueues Celery job → returns immediately. Worker pipeline:

1. **Extract** (dispatch by `source_type`):
   - PDF → text-layer via `unstructured`/`pdfplumber`; **OCR fallback** (Tesseract) for scanned pages
   - DOCX → `unstructured` (preserves headings/tables)
   - XLSX/CSV → per-sheet, **table-aware** (row/table chunks, not flat text)
   - TXT/MD → direct
   - Image → OCR text (+ optional vision-caption hook, deferred)
   - Website → fetch + `trafilatura` clean text; single-URL now, full crawl deferred
2. **Chunk** — structure-aware (respect headings/page/sheet boundaries), configurable size + overlap; capture source metadata per chunk (page/sheet/url/heading) for citations
3. **Embed** — batch chunks through `EmbeddingProvider` (OpenAI `text-embedding-3-small`, 1536-dim); generate sparse vectors too (for hybrid)
4. **Store** — write chunk rows to Postgres, upsert vectors + payload to Qdrant; update `document.status=ready` (or `failed` + error)

Cross-cutting: dedup via `content_hash`; idempotent re-index (delete old chunks → re-ingest) for changed websites; per-document status polled by frontend.

---

## RAG Query Pipeline

1. Receive question + optional collection filter + conversation_id
2. (If follow-up) condense question using conversation history
3. Embed query → **retrieve** top-K chunks from Qdrant with payload filter `org_id` (+collection)
4. **Hybrid search** (Qdrant native dense + sparse with fusion) — included early; meaningfully improves accuracy
5. Build grounded prompt ("answer **only** from context; if not present, say you don't know")
6. Call `LLMProvider` (OpenAI) → **stream** answer to client via SSE
7. Return answer + **citations** (source doc, page/sheet/url per chunk) — non-negotiable
8. Persist messages + cited_chunk_ids; accept thumbs up/down feedback

Reranking (cross-encoder) and conversational memory: interfaces stubbed, full impl deferred.

---

## API Surface (FastAPI)

- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
- `POST /orgs`, `GET /orgs`, `POST /orgs/{id}/invite`
- `POST /collections`, `GET /collections`
- `POST /documents` (file upload), `POST /documents/url` (website), `GET /documents` (list+status), `DELETE /documents/{id}`, `POST /documents/{id}/reindex`
- `POST /chat` (SSE streaming answer + citations), `GET /conversations`, `GET /conversations/{id}`
- `POST /feedback`

All endpoints resolve tenant from JWT and enforce role; all DB access scoped by `org_id`.

---

## Frontend (Next.js)

- Auth pages (register/login), org switcher
- Collections dashboard
- Upload UI (drag-drop files + add-URL) with **per-document status** (queued/processing/ready/failed) via polling
- Chat interface: streaming answers, inline **citations** linking to source, follow-up support, thumbs up/down
- Document management (list, delete, re-index)

---

## Repository Layout

```
RAG/
├── README.md
├── PLAN.md
├── CHECKLIST.md
├── backend/
│   ├── docker-compose.yml      # postgres, qdrant, redis, minio (+ api/worker later)
│   ├── .env.example
│   ├── requirements.txt
│   ├── alembic/                # migrations
│   └── app/
│       ├── main.py             # FastAPI app
│       ├── config.py
│       ├── db.py               # session, RLS setup
│       ├── celery_app.py       # Celery instance
│       ├── models/             # SQLAlchemy models
│       ├── api/                # routers (auth, orgs, collections, documents, chat, feedback)
│       ├── auth/               # JWT, tenant/role deps
│       ├── ingestion/
│       │   ├── extractors/     # pdf, docx, excel, text, image, website
│       │   ├── chunking.py
│       │   └── tasks.py        # Celery tasks
│       ├── rag/
│       │   ├── retriever.py    # LangChain hybrid retriever (Qdrant dense+sparse)
│       │   └── pipeline.py     # LCEL chain: prompt build + generation
│       ├── providers/
│       │   ├── base.py         # LLMProvider, EmbeddingProvider interfaces
│       │   └── openai_provider.py
│       └── vectorstore/
│           ├── base.py         # VectorStore interface
│           └── qdrant_store.py
└── (frontend/ — deferred; not built yet)
```

---

## Build Milestones (within this phase)

1. **Scaffold & infra** — docker-compose (postgres, qdrant, redis, minio), FastAPI + Next.js skeletons, config/env, Alembic.
2. **Auth & multi-tenancy** — org/user/membership models, JWT, tenant+role deps, RLS. *Foundation everything else depends on.*
3. **Provider + vector-store abstractions** — interfaces + OpenAI + pgvector impls.
4. **Ingestion (upload → ready)** — object storage, document model/status, Celery, extractors (start PDF/DOCX/TXT/CSV-XLSX), chunking, embedding, storage. Image OCR + website next.
5. **RAG query** — retriever (hybrid), grounded prompt, SSE streaming, citations, chat persistence.
6. **Frontend** — auth, upload+status, chat with citations, doc management.
7. **Feedback + polish** — thumbs up/down, error handling, basic usage logging.

---

## Scalability Boundaries (designed in now, scaled later)

- **Async ingestion** from day 1 (Celery/Redis) — the single most important decision.
- **Stateless API** — scale horizontally; no in-process state.
- **Swappable AI** — provider interface; OpenAI now, any model later via config.
- **Qdrant from day 1** behind a `VectorStore` interface — payload filtering + hybrid built in; per-tenant collections available at higher scale without app changes.
- **`org_id`-filtered vectors** (Qdrant payload filter) — multi-tenant isolation baked in.
- **Container-first** — runs locally, ports to any cloud unchanged.

Explicitly deferred (boundaries left in place): reranking, full conversational memory, vision captioning, full-site crawling, billing/Stripe, SSO/SCIM, connectors (Drive/Slack), advanced analytics.

---

## Verification (end-to-end)

1. `docker-compose up` — all services healthy (api, worker, postgres, qdrant, redis, minio).
2. Register a user → an org is created; register a second org → confirm data isolation (org A cannot see org B's documents/chunks via API).
3. Upload one of each: a text-layer PDF, a scanned PDF (verify OCR path), a DOCX, an XLSX, a TXT, an image, and add a website URL. Confirm each `document.status` transitions queued→processing→ready (failures show error).
4. Verify chunk rows exist in Postgres and corresponding vectors exist in Qdrant (with `org_id` payload) for each document.
5. Ask a question answerable from an uploaded doc → answer **streams**, is grounded, and shows **citations** linking to the correct source (page/sheet/url).
6. Ask a question with no relevant content → system responds "I don't know" rather than hallucinating.
7. Ask a follow-up referencing the prior turn → confirm conversation context works.
8. Submit thumbs up/down → feedback persisted.
9. Delete a document → its chunks/vectors are removed; re-index a website → chunks refreshed.
10. (Provider swap smoke test) Point the provider config at an alternate embedding/LLM impl/stub → confirm app runs without code changes.

---

## Changelog

- **2026-06-09** — Initial plan drafted. Decisions locked: Python/FastAPI + Next.js, multi-tenant from day 1, container-first, OpenAI behind provider abstraction.
- **2026-06-09** — Updated: **Qdrant from day 1** (replaces pgvector; Postgres now metadata-only, tenant isolation via Qdrant payload filter, native hybrid search). Orchestration set to **LangChain ecosystem** (loaders, splitters, retrievers, LCEL) instead of LlamaIndex.
- **2026-06-09** — Dependency management: use **`requirements.txt`** (not `pyproject.toml`).
- **2026-06-10** — `docker-compose.yml` + `.env.example` moved **into `backend/`** (frontend deferred, so the project is backend-self-contained for now); `config.py` loads `backend/.env`.
- **2026-06-10** — `docker-compose.yml` written + adversarially verified (web-backed). Pinned image tags (qdrant v1.18.2, redis 7.4-alpine, postgres 16-alpine, dated MinIO/mc releases); `mc ready local` healthcheck for MinIO; Qdrant has no in-container healthcheck (distroless) — checked via host/`/health`; ports bound to 127.0.0.1; added `REDIS_PORT` to env.
- **2026-07-05** — **Step 8 (Frontend):** Next.js 16 (App Router, TS, **Tailwind v4**) app in `frontend/` — semantic-token design system with light/dark, typed API client + JWT auth context, auth pages + route guard, app shell, BYOK settings, drag-drop document upload with live status polling, and SSE-streamed cited chat. See [docs/step-08-frontend.md](docs/step-08-frontend.md).
- **2026-07-05** — **Step 9 (Analytics):** per-request `usage_events` table + token capture from streamed LLM responses (`usage_metadata`); `GET /analytics/me` and `/analytics/org` (owner/admin, per-user breakdown); frontend dashboard (stat tiles + Recharts, CVD-validated palette) with an admin org/me scope toggle. See [docs/step-09-analytics.md](docs/step-09-analytics.md).
