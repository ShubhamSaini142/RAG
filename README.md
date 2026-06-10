# RAG Knowledge Base

A multi-tenant, RAG-based knowledge-base SaaS. Users upload/connect content
(PDF, DOCX, Excel/CSV, text, images, websites); the system extracts → chunks →
embeds → stores it, then answers natural-language questions grounded in the
content, **with citations**.

See [PLAN.md](PLAN.md) for the full architecture and roadmap.

## Stack

- **Backend:** Python · FastAPI · Celery + Redis
- **Vector store:** Qdrant (from day 1)
- **Metadata DB:** Postgres
- **Object storage:** MinIO / S3
- **RAG:** LangChain ecosystem · OpenAI (behind a swappable provider interface)
- **Frontend:** Next.js *(not scaffolded yet)*

## Project Structure (backend)

```
RAG/
├── README.md
├── PLAN.md                       # architecture + roadmap (living doc)
├── CHECKLIST.md                  # step-by-step build checklist
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

## Status

Scaffold in place. Next: `docker-compose` for Postgres + Qdrant + Redis + MinIO,
then DB models/migrations, auth & multi-tenancy, and the first ingest→ask slice.

## License

Personal repository. All rights reserved unless stated otherwise.
