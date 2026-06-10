# RAG Knowledge Base — Build Checklist

A step-by-step checklist for building the project. Check items off as you go.
See [PLAN.md](PLAN.md) for the full architecture and [README.md](README.md) for structure.

---

## Step 0 — Prerequisites (one-time machine setup)

- [x] Python 3.11+ installed (have 3.12.7)
- [x] git installed
- [x] Node.js + npm installed (have Node 24.16 — for the frontend later)
- [x] Docker Desktop installed (4.77)
- [x] WSL2 features enabled via `wsl --install`
- [x] **Reboot the PC** to activate WSL2 / Virtual Machine Platform
- [x] Launch Docker Desktop once → accept license → wait for "running"
- [x] OpenAI API key available (still needs to be pasted into `backend/.env` before Step 6)

## Step 1 — Scaffold the backend ✅

- [x] Folder tree under `backend/app/` (api, auth, models, ingestion, rag, providers, vectorstore)
- [x] `requirements.txt`
- [x] `.env.example`
- [x] `config.py`, `db.py`, `main.py`, `celery_app.py`
- [x] `/health` endpoint
- [x] Structure documented in `README.md`

## Step 2 — Infrastructure via docker-compose  ◀ YOU ARE HERE

> Everything runs from `backend/` (compose + .env live there now).

- [x] `backend/docker-compose.yml` for Postgres + Qdrant + Redis + MinIO (verified, pinned tags)
- [x] Reboot done + Docker Desktop **running** (engine 29.5.3, compose v5.1.4)
- [x] `cd backend` then `copy .env.example .env` (OPENAI_API_KEY still to fill)
- [x] `docker compose up -d`
- [x] `docker compose ps` → postgres, redis, minio show **healthy**
- [x] Qdrant reachable: `/readyz` → "all shards are ready" (dashboard: http://localhost:6333/dashboard)
- [x] MinIO console reachable: http://localhost:9001 (login minioadmin/minioadmin)
- [x] `rag-documents` bucket created (rag-createbuckets exited 0)

## Step 3 — Backend "hello world"

- [ ] From `backend/`: `python -m venv .venv` + activate
- [ ] `pip install -r requirements.txt`
- [ ] `uvicorn app.main:app --reload`
- [ ] Open http://localhost:8000/health → `status: ok` with postgres + qdrant both `ok`

## Step 4 — Database schema + migrations

- [ ] SQLAlchemy models: organizations, users, memberships, collections, documents, chunks, conversations, messages, feedback (`org_id` on every domain table)
- [ ] `alembic init` + configure to use `settings.database_url`
- [ ] Autogenerate + apply first migration
- [ ] (Optional) Enable Postgres Row-Level Security as a tenant safety net

## Step 5 — Auth & multi-tenancy

- [ ] Password hashing + JWT create/verify (`auth/jwt.py`)
- [ ] `auth/deps.py`: current-user, current-org, role-check dependencies
- [ ] Endpoints: register, login, me; create org; invite member
- [ ] Verify org isolation: org A cannot read org B's data

## Step 6 — First vertical slice (ingest → ask)

- [ ] Implement provider impls (`OpenAIEmbeddingProvider`, `OpenAILLMProvider`)
- [ ] Implement `QdrantStore` (ensure_collection, upsert, search, delete)
- [ ] Upload a single **.txt** file → store to MinIO → create document row
- [ ] Celery task: extract → chunk → embed → upsert to Qdrant → mark ready
- [ ] `POST /chat`: retrieve (tenant-scoped) → grounded prompt → **stream** answer
- [ ] Answer includes **citations**; "I don't know" when no relevant context

---

## After the slice works — widen coverage

- [ ] More source types: PDF (+OCR), DOCX, Excel/CSV, images (OCR), websites
- [ ] Hybrid search (Qdrant dense + sparse)
- [ ] Conversation memory (follow-up questions)
- [ ] Thumbs up/down feedback
- [ ] Collections management (list, delete, re-index)
- [ ] Frontend (Next.js): auth, upload + status, chat with citations
- [ ] Usage logging + error handling polish

## Later (deferred — boundaries already in place)

- [ ] Reranking (cross-encoder)
- [ ] Vision captioning for images
- [ ] Full-site crawling
- [ ] Billing / plans (Stripe)
- [ ] SSO / SCIM
- [ ] Connectors (Drive, Slack, Notion)
- [ ] Analytics dashboard
