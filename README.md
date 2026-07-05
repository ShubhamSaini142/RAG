# RAG Knowledge Base

A multi-tenant, RAG-based knowledge-base SaaS. Users upload/connect content
(PDF, DOCX, Excel/CSV, text, images, websites); the system extracts → chunks →
embeds → stores it, then answers natural-language questions grounded in the
content, **with citations**.

> 👉 **New here? Start with [SETUP.md](SETUP.md)** — fresh machine to a running app, step by step.

See [PLAN.md](PLAN.md) for the full architecture and roadmap, [docs/CHECKLIST.md](docs/CHECKLIST.md)
for build progress, and [docs/](docs/) for per-step deep-dives + collaborator setup:

- **[docs/api-reference.md](docs/api-reference.md) — full API reference (every endpoint, curl, steps)**
- [docs/step-04-database-schema.md](docs/step-04-database-schema.md) — DB models, migrations & how to apply them
- [docs/step-05-auth.md](docs/step-05-auth.md) — auth & multi-tenancy (JWT, roles) + git workflow
- [docs/step-06-rag-slice.md](docs/step-06-rag-slice.md) — the RAG slice (ingest → ask), worker setup, Swagger
- [docs/step-07-byok-providers.md](docs/step-07-byok-providers.md) — bring-your-own-key + multi-provider (per-org, encrypted)
- [docs/step-08-frontend.md](docs/step-08-frontend.md) — Next.js UI (design system, auth, upload, chat) + collaborator setup
- [docs/step-09-analytics.md](docs/step-09-analytics.md) — usage analytics + token tracking (per-user & org-wide)

## Stack

- **Backend:** Python · FastAPI · Celery + Redis
- **Vector store:** Qdrant (from day 1)
- **Metadata DB:** Postgres
- **Object storage:** MinIO / S3
- **RAG:** LangChain ecosystem · **BYOK multi-provider** (OpenAI / Anthropic / Gemini / OpenAI-compatible), per-org encrypted keys
- **Frontend:** Next.js (App Router, TypeScript) · Tailwind v4 design system · Recharts

## Project Structure (backend)

```
RAG/
├── README.md
├── PLAN.md                       # architecture + roadmap (living doc)
├── docs/                         # per-step deep-dives + collaborator setup
│   ├── CHECKLIST.md              # step-by-step build checklist
│   └── step-04-database-schema.md
└── backend/
    ├── docker-compose.yml        # Postgres + Qdrant + Redis + MinIO
    ├── .env.example              # copy to .env and fill in
    ├── requirements.txt
    ├── alembic/                  # DB migrations (initialised later)
    └── app/
        ├── main.py               # FastAPI app + router wiring
        ├── config.py             # settings from env (.env)
        ├── db.py                 # SQLAlchemy engine, session, Base
        ├── celery_app.py         # Celery instance (async ingestion)
        ├── api/
        │   └── health.py         # /health — checks Postgres + Qdrant
        ├── auth/                 # JWT, tenant/role deps (multi-tenancy)
        ├── models/               # SQLAlchemy ORM models (org_id everywhere)
        ├── ingestion/
        │   ├── extractors/       # one per source type (pdf, docx, excel, ...)
        │   ├── chunking.py       # structure-aware chunking
        │   └── tasks.py          # Celery ingestion pipeline
        ├── rag/
        │   ├── retriever.py      # hybrid search over Qdrant (tenant-scoped)
        │   └── pipeline.py       # LCEL chain: prompt → generate → cite
        ├── providers/
        │   ├── base.py           # LLMProvider / EmbeddingProvider interfaces
        │   └── openai_provider.py
        └── vectorstore/
            ├── base.py           # VectorStore interface
            └── qdrant_store.py   # Qdrant implementation
```

> Many modules are intentional scaffold stubs (`NotImplementedError`) — they're
> filled in milestone by milestone per [PLAN.md](PLAN.md).

## Getting Started (backend)

```powershell
# Everything backend lives in backend/ for now.
cd backend
copy .env.example .env              # then fill in OPENAI_API_KEY

# 1) Start infrastructure (needs Docker Desktop running)
docker compose up -d
docker compose ps                   # postgres/redis/minio -> healthy

# 2) Python deps + run the API
python -m venv .venv
.venv\Scripts\activate              # Windows (PowerShell)
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check: open http://localhost:8000/health (Postgres + Qdrant should be `ok`).
Qdrant dashboard: http://localhost:6333/dashboard · MinIO console: http://localhost:9001

## Getting Started (frontend)

With the backend running (and a worker), start the UI:

```powershell
cd frontend
copy .env.example .env.local        # points at http://localhost:8000
npm install
npm run dev                         # http://localhost:3000
```

Open http://localhost:3000 → register → configure your provider keys in **Settings** →
upload a document → **Chat**. See [docs/step-08-frontend.md](docs/step-08-frontend.md).

## Status

Backend complete through **BYOK multi-provider** + **usage analytics**; a **Next.js
frontend** covers auth, provider settings, document upload, streamed cited chat, and the
analytics dashboard. Next: more source types (PDF/DOCX/Excel/images/websites), hybrid
search, conversation memory.

## License

Personal repository. All rights reserved unless stated otherwise.
