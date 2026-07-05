# FINAL SETUP — RAG Knowledge Base (fresh machine → running app)

The single, complete guide: exact **versions**, every **install**, and every **command
to start the app** (backend + worker + frontend). Commands are **Windows PowerShell**
(the project's primary environment); macOS/Linux notes where they differ.

> Deeper per-feature detail lives in [SETUP.md](SETUP.md) and [docs/](docs/). This file
> is the quick, authoritative "what to install and how to run it".

---

## 1. Versions (what's installed / expected)

| Tool | Version (tested) | Notes |
|------|------------------|-------|
| **Node.js** | **v24.16.0** (any 18+ works; use LTS) | frontend |
| **npm** | **11.13.0** (ships with Node) | frontend deps |
| **Python** | **3.12.7** (3.11+ works) | backend |
| **Docker Desktop** | **29.5.3** (engine) | runs the 4 services |
| **Docker Compose** | **v5.1.4** (bundled) | `docker compose …` |
| **Git** | any recent | clone |

**App stack (installed automatically by the steps below — no manual action):**

| Layer | Version |
|-------|---------|
| Next.js | 16.2.10 (App Router, Turbopack) |
| React | 19.2.4 |
| Tailwind CSS | v4 |
| Recharts | 3.9.2 |
| FastAPI / Uvicorn / SQLAlchemy 2 / Alembic / Celery | via `backend/requirements.txt` |

**Container images (pinned in `backend/docker-compose.yml`):**

| Service | Image |
|---------|-------|
| Postgres | `postgres:16-alpine` |
| Qdrant | `qdrant/qdrant:v1.18.2` |
| Redis | `redis:7.4-alpine` |
| MinIO | `minio/minio:RELEASE.2025-09-07T16-13-09Z` |

---

## 2. Install prerequisites (one-time)

```powershell
winget install OpenJS.NodeJS.LTS      # Node + npm
winget install Python.Python.3.12     # Python
winget install Docker.DockerDesktop   # Docker Desktop
winget install Git.Git                # Git
```
> macOS: `brew install node python@3.12 git` + install Docker Desktop from docker.com.

**Docker on Windows needs WSL2.** If Docker won't start:
```powershell
wsl --install --no-distribution      # enable required Windows features
# then REBOOT, launch Docker Desktop once, wait for "Engine running"
docker info                           # should print server info, not an error
```

Close and reopen your terminal after installing so `node`, `python`, `docker` are on PATH.

---

## 3. Get the code

```powershell
git clone https://github.com/ShubhamSaini142/RAG.git
cd RAG
git checkout UAT
```

---

## 4. Backend — configure `.env` (one-time)

```powershell
cd backend
copy .env.example .env
```
Edit `backend/.env` and set an **encryption key** (encrypts per-org provider keys):
```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Paste the output as `ENCRYPTION_KEY=...` in `backend/.env`.

> No `OPENAI_API_KEY` needed here — AI keys are **bring-your-own**, added per org in the
> app UI (step 8). Service hosts use `127.0.0.1` (already set) — do not change to
> `localhost` (avoids a first-request IPv6 hang). Never commit `.env`.

---

## 5. Start the infrastructure (Docker)

```powershell
# from backend/
docker compose up -d        # Postgres + Qdrant + Redis + MinIO
docker compose ps           # postgres/redis/minio -> "healthy"
```

| Service | URL / port |
|---------|-----------|
| Postgres | `127.0.0.1:5438` |
| Qdrant | http://localhost:6333/dashboard |
| Redis | `127.0.0.1:6379` |
| MinIO console | http://localhost:9101 (`minioadmin` / `minioadmin`) |

---

## 6. Backend — Python env, dependencies, database

```powershell
# from backend/
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                   # create all tables (incl. usage_events)
```
> If PowerShell blocks activation: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (once), then activate again.

---

## 7. Frontend — dependencies

```powershell
cd ..\frontend
copy .env.example .env.local          # already points at http://localhost:8000
npm install
```

---

## 8. ▶️ Start the app (the commands you'll use every time)

You need **infra up** (step 5) plus **three terminals**. Each backend terminal must have
the venv activated (`.\.venv\Scripts\Activate.ps1`).

```powershell
# Terminal 1 — API  (from backend/)
uvicorn app.main:app --reload
```
```powershell
# Terminal 2 — Celery worker  (from backend/) — REQUIRED to index uploads
celery -A app.celery_app worker --loglevel=info --pool=solo
```
```powershell
# Terminal 3 — Frontend  (from frontend/)
npm run dev
```

Open the app:

| What | URL |
|------|-----|
| **Web app** | **http://localhost:3000** |
| API health | http://localhost:8000/health → `{"status":"ok",...}` |
| API docs (Swagger) | http://localhost:8000/docs |

> On Windows the Celery worker **must** use `--pool=solo`. Without a running worker,
> uploaded documents stay `queued` and never become `ready`.

---

## 9. First use (in the web app)

1. **Register** at http://localhost:3000 → you land on **Settings**.
2. **Settings** → add your **embedding** provider + key (validates + detects dimension),
   then your **chat** provider + key. (OpenAI / Anthropic / Gemini / OpenAI-compatible.)
3. **Documents** → drag-drop a `.txt` / `.md` (≤ 10 MB) → wait for **Ready**.
4. **Chat** → ask a question → streamed answer with **sources**; use **New chat** and the
   sidebar to manage conversations.
5. **Analytics** → token usage + activity (owners/admins can switch to the whole org).

---

## Daily quick-start (everything already installed)

```powershell
# 1) infra
cd RAG\backend ; docker compose up -d

# 2) API           (new terminal, in backend/)
.\.venv\Scripts\Activate.ps1 ; uvicorn app.main:app --reload

# 3) worker        (new terminal, in backend/)
.\.venv\Scripts\Activate.ps1 ; celery -A app.celery_app worker --loglevel=info --pool=solo

# 4) frontend      (new terminal, in frontend/)
npm run dev
```
Stop infra when done: `docker compose stop` (keeps data) · `docker compose down -v` (⚠️ deletes data).

---

## Run the tests (backend; no real AI key needed)

```powershell
cd backend ; .\.venv\Scripts\Activate.ps1
python -m tests.test_auth
python -m tests.test_providers
python -m tests.test_rag
python -m tests.test_analytics
python -m tests.test_conversations
```

Frontend checks:
```powershell
cd frontend
npx tsc --noEmit      # typecheck
npm run build         # production build
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Docker won't start | Enable WSL2 (`wsl --install --no-distribution`) + reboot; open Docker Desktop once. |
| First API request hangs ~130s | Use `127.0.0.1` in `.env` (already the default), not `localhost`. |
| Uploaded doc stuck at `queued` | The Celery worker isn't running — start Terminal 2 (`--pool=solo`). |
| `409` on upload/chat | Configure providers first (Settings, step 9.2). |
| First provider-key save is slow | One-time cold import + a live validation probe; subsequent saves are fast. |
| Frontend can't reach API | Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`. |
| PowerShell won't activate venv | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate. |
| Port in use (3000/8000/5438/6333/9101) | Stop the other process, or change the port in `.env` / `docker-compose.yml`. |
| `ModuleNotFoundError: app` | Run backend commands from `backend/`; for tests use `python -m tests.<name>`. |

---

## Ports summary

| Port | Service |
|------|---------|
| 3000 | Frontend (Next.js) |
| 8000 | Backend API (FastAPI) |
| 5438 | Postgres |
| 6333 / 6334 | Qdrant (HTTP / gRPC) |
| 6379 | Redis |
| 9100 / 9101 | MinIO (API / console) |
