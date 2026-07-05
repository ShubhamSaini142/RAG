# Setup Guide — RAG Knowledge Base

Everything needed to go from a **fresh machine** to a **running, queryable** RAG app.
This is a living document — keep it updated as the project evolves.

> Commands are written for **Windows PowerShell** (the project's primary environment);
> macOS/Linux equivalents are noted where they differ. For deeper per-feature detail
> see [docs/](docs/) and the full [API reference](docs/api-reference.md).

**What you'll have running at the end:** Postgres + Qdrant + Redis + MinIO (in Docker),
a FastAPI backend, a Celery worker, and a working upload → ask flow with your own AI keys.

---

## 0. Prerequisites (one-time)

| Tool | Why | Install (Windows) |
|------|-----|-------------------|
| **Python 3.11+** | backend | `winget install Python.Python.3.12` |
| **Docker Desktop** | runs Postgres/Qdrant/Redis/MinIO | `winget install Docker.DockerDesktop` |
| **Git** | clone the repo | `winget install Git.Git` |
| **Node.js** (optional) | future frontend | `winget install OpenJS.NodeJS.LTS` |

**Docker on Windows needs WSL2.** If Docker won't start:
```powershell
wsl --install --no-distribution    # enables the required Windows features
# then REBOOT (Windows only activates them after a restart)
```
After reboot, open **Docker Desktop** once and wait for **"Engine running"**. Verify:
```powershell
docker info        # should print server info, not an error
```

---

## 1. Get the code

```powershell
git clone https://github.com/ShubhamSaini142/RAG.git
cd RAG
git checkout UAT          # current integration branch
```
Everything below runs from the **`backend/`** folder:
```powershell
cd backend
```

---

## 2. Configure environment (`.env`)

```powershell
copy .env.example .env
```
Then edit `backend/.env`:

1. **`ENCRYPTION_KEY`** (required) — encrypts per-org provider keys. Generate one:
   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Paste the output as `ENCRYPTION_KEY=...`.
2. **Service hosts use `127.0.0.1`, not `localhost`** — already set. (Docker publishes
   IPv4-only; `localhost` can resolve to IPv6 and cause a ~130s hang on the first request.)
3. **No `OPENAI_API_KEY` needed here** — AI keys are bring-your-own, configured **per
   organization** at runtime (step 7), not in `.env`.

> ⚠️ Save `.env` with **LF** line endings (not CRLF) — a trailing `\r` can corrupt values.
> `.env` is git-ignored; never commit it.

---

## 3. Start the infrastructure (Docker)

```powershell
docker compose up -d        # Postgres + Qdrant + Redis + MinIO
docker compose ps           # postgres/redis/minio should be "healthy"
```
Reachable at:

| Service | URL / port |
|---------|-----------|
| Postgres | `127.0.0.1:5438` |
| Qdrant | http://localhost:6333/dashboard (gRPC 6334) |
| Redis | `127.0.0.1:6379` |
| MinIO API / Console | http://localhost:9100 / http://localhost:9101 (`minioadmin` / `minioadmin`) |

(Qdrant has no in-container healthcheck by design; confirm with `curl http://localhost:6333/readyz`.)

---

## 4. Python environment + dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```
> If PowerShell blocks the activate script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once), then activate again.

**Point VS Code at the venv** (so imports resolve): `Ctrl+Shift+P` → *Python: Select
Interpreter* → `backend/.venv/Scripts/python.exe`. (Opening the `RAG` folder as the
workspace makes `.vscode/settings.json` do this automatically.)

---

## 5. Create the database tables (migrations)

```powershell
alembic upgrade head
```
Creates all tables (organizations, users, documents, chunks, provider_settings, …).
Verify: `alembic current` shows the latest revision.

---

## 6. Run the app + worker

Two terminals (both with the venv activated, from `backend/`):

```powershell
# Terminal 1 — API
uvicorn app.main:app --reload
```
```powershell
# Terminal 2 — Celery worker (REQUIRED to process uploads)
celery -A app.celery_app worker --loglevel=info --pool=solo
```
> On Windows use `--pool=solo`. Without a running worker, uploaded documents stay `queued`.

**Check it's alive:**
```powershell
curl http://localhost:8000/health      # {"status":"ok","checks":{"postgres":"ok","qdrant":"ok"}}
```
Open the interactive docs: **http://localhost:8000/docs**

---

## 7. Create an account + configure your AI provider (BYOK)

Easiest via **Swagger UI** (`/docs`) — or curl. Each org brings its **own** keys.

```powershell
# 7a. Register -> returns access_token (save it)
curl.exe -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" `
  -d '{\"email\":\"you@example.com\",\"password\":\"password123\",\"name\":\"You\"}'

# In /docs: click Authorize and paste the token. With curl, set:  $T = "<access_token>"

# 7b. Configure embeddings (validates the key + auto-detects dimension)
curl.exe -X PUT http://localhost:8000/settings/providers/embedding -H "Authorization: Bearer $T" `
  -H "Content-Type: application/json" `
  -d '{\"provider\":\"openai\",\"model\":\"text-embedding-3-small\",\"api_key\":\"sk-...\"}'

# 7c. Configure the chat LLM (OpenAI / Anthropic / Gemini / openai_compatible)
curl.exe -X PUT http://localhost:8000/settings/providers/llm -H "Authorization: Bearer $T" `
  -H "Content-Type: application/json" `
  -d '{\"provider\":\"anthropic\",\"model\":\"claude-sonnet-4-6\",\"api_key\":\"sk-ant-...\"}'
```
Keys are stored **encrypted**; uploads/chat return `409` until both are configured.
See provider/model options in the [API reference](docs/api-reference.md#settings--ai-providers-byok).

---

## 8. Use it — upload a document and ask

```powershell
# Upload (.txt / .md). Then poll /documents/{id} until status == "ready".
curl.exe -X POST http://localhost:8000/documents -H "Authorization: Bearer $T" `
  -F "file=@notes.txt;type=text/plain"

# Ask — streamed (SSE) answer with citations
curl.exe -N -X POST http://localhost:8000/chat -H "Authorization: Bearer $T" `
  -H "Content-Type: application/json" -d '{\"question\":\"What is in my document?\"}'
```
Full request/response details: [docs/api-reference.md](docs/api-reference.md).

---

## 9. Run the tests (no real AI key needed)

```powershell
python -m tests.test_auth        # auth + multi-tenant isolation
python -m tests.test_providers   # BYOK: encrypted-at-rest, masked, dim auto-detect
python -m tests.test_rag         # full slice: gate -> ingest -> cited answer -> isolation
```
These patch the AI providers with deterministic fakes, so they exercise the whole
pipeline against real Postgres/Qdrant/MinIO without calling OpenAI/Anthropic/Gemini.

---

## 10. Run the web UI (frontend)

With the backend + worker running, start the Next.js app in a new terminal:

```powershell
cd frontend
copy .env.example .env.local          # already points at http://localhost:8000
npm install
npm run dev                            # http://localhost:3000
```

Open **http://localhost:3000** → **Register** → you'll land on **Settings** to add your
own embedding + chat provider keys → **Documents** (upload a `.txt`/`.md`) → **Chat**
(streamed, cited answers) → **Analytics** (token usage; owners/admins see the whole org).

> If the API isn't on `localhost:8000`, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.
> Full detail: [docs/step-08-frontend.md](docs/step-08-frontend.md) ·
> [docs/step-09-analytics.md](docs/step-09-analytics.md).

---

## Daily commands

```powershell
docker compose up -d / stop / down          # start / pause / remove infra (data kept)
docker compose down -v                       # ⚠️ also deletes all data volumes
uvicorn app.main:app --reload                # API (from backend/)
celery -A app.celery_app worker --pool=solo  # worker (from backend/)
alembic upgrade head                          # apply new migrations (from backend/)
alembic revision --autogenerate -m "msg"      # create a migration after model changes
npm run dev                                    # frontend (from frontend/)
```

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| First request hangs ~130s | `localhost` → IPv6. Use `127.0.0.1` in `.env` (already the default). |
| Uploaded doc stuck at `queued` | No Celery worker running — start it (`--pool=solo` on Windows). |
| `409` on upload/chat | Configure providers first (step 7). |
| `ModuleNotFoundError: app` | Run from `backend/` (and for tests use `python -m tests.<name>`). |
| `ENCRYPTION_KEY` error | Set a valid Fernet key in `.env` (step 2). |
| Editor shows "import could not be resolved" | Point VS Code at `backend/.venv` (step 4) — code still runs fine. |
| Port already in use (5438/6333/9100/8000) | Change the host port in `.env` / `docker-compose.yml`. |

## Project layout (current)

```
RAG/
├── README.md · SETUP.md (this) · PLAN.md
├── docs/                      api-reference.md, CHECKLIST.md, step-04…09 deep-dives
├── backend/
│   ├── docker-compose.yml · .env.example · requirements.txt · alembic/
│   └── app/
│       ├── main.py · config.py · db.py · celery_app.py · crypto.py · storage.py
│       ├── api/        health, auth, orgs, documents, chat, settings, analytics
│       ├── auth/       JWT, deps, role checks
│       ├── models/     org, user, collection, document, chunk, conversation, feedback, provider_settings, usage
│       ├── providers/  base, registry (redirector), openai/anthropic/gemini/openai_compatible, factories
│       ├── analytics/  usage recording + aggregation
│       ├── ingestion/  extractors, chunking, Celery tasks
│       ├── rag/        retriever, pipeline
│       └── vectorstore/ base, qdrant_store (per-org collections)
└── frontend/                  Next.js (App Router, TS, Tailwind v4)
    └── src/
        ├── app/       login, register, (app)/{chat,documents,settings,analytics}
        ├── components/ brand, app-shell, ui/* (design system)
        └── lib/       api, types, auth, theme
```

## Status

Steps 0–9 complete: machine setup → infra → DB schema → auth & multi-tenancy →
RAG slice (ingest → cited answer) → async serving path → BYOK multi-provider →
**Next.js frontend** → **usage analytics + token tracking**.
Next candidates: more file types (PDF/Excel/images/websites), hybrid search, conversation memory.
