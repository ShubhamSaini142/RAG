# Step 4 — Database Schema & Migrations

This document explains the database layer of the RAG backend (what it is, why it's
built this way) **and** gives setup steps for a collaborator who clones the repo.

- **Explanation** → understand the design.
- **Setup for collaborators** → jump to [Setup](#setup-for-collaborators) to get your local DB schema running.

---

## What this step delivers

The 9 application tables that everything else depends on, created in Postgres via a
**versioned migration** so every machine (yours, a teammate's, production) ends up
with the identical schema from one command.

Tables: `organizations`, `users`, `memberships`, `collections`, `documents`,
`chunks`, `conversations`, `messages`, `feedback` (+ `alembic_version`, managed by
Alembic).

---

## The mental model: 3 layers

```
1. MODELS (Python classes)        →  hand-written in backend/app/models/
        ↓ Alembic compares models to the live DB
2. MIGRATION (a Python script)    →  Alembic auto-generates this
        ↓ "alembic upgrade head"
3. TABLES (real tables in Postgres)
```

- **Models** = the desired shape, in Python.
- **Migration** = the instructions to make the DB match the models.
- **Tables** = the actual result in Postgres.

---

## Files

**Models** (`backend/app/models/`):

| File | Contains |
|------|----------|
| `base.py` | Reusable mixins: UUID primary key + `created_at`/`updated_at` |
| `enums.py` | Allowed values (roles, statuses, source types) |
| `organization.py` | `Organization` |
| `user.py` | `User`, `Membership` |
| `collection.py` | `Collection` |
| `document.py` | `Document`, `Chunk` |
| `conversation.py` | `Conversation`, `Message` |
| `feedback.py` | `Feedback` |
| `__init__.py` | Imports every model so Alembic can discover them |

**Alembic** (`backend/`):

| File | Purpose |
|------|---------|
| `alembic.ini` | Config: where migrations live, logging |
| `alembic/env.py` | Connects Alembic to our DB (`settings.database_url`) + models (`Base.metadata`) |
| `alembic/script.py.mako` | Template for new migration files |
| `alembic/versions/910f929fd87a_initial_schema.py` | The generated initial migration |

---

## Building blocks

### `base.py` — mixins (don't repeat yourself)

Every table needs an id + timestamps, so they live in two reusable mixins:

```python
class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

class TimestampMixin:
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- **UUID primary keys** (not auto-increment 1,2,3): unguessable, don't leak row counts, no cross-system collisions — the right choice for a SaaS.
- **`server_default=func.now()`**: the database fills the timestamp, reliable even for inserts outside our app.
- **`onupdate=func.now()`**: `updated_at` refreshes on every change.
- **`timezone=True`**: timezone-aware timestamps (avoids UTC-vs-local bugs).

### `enums.py` — allowed values, stored as strings

`Role` (owner/admin/editor/viewer), `DocumentStatus` (queued/processing/ready/failed),
`SourceType` (pdf/docx/xlsx/xls/csv/txt/image/website), `MessageRole`, `FeedbackRating`.

> **Why stored as plain `String`, not a native Postgres ENUM:** native enums are painful
> to extend (adding a value can lock the table). Strings + Python constants give us
> validation in code with freedom to add new values later with zero DB pain.

---

## The 9 tables

### Tenancy core
- **`organizations`** — the tenant; root of all data (`name`, `plan`).
- **`users`** — a person (`email` unique+indexed, `hashed_password`, `name`). We store a
  *hash*, never the real password.
- **`memberships`** — links a user to an org **with a role**. A user can be in multiple
  orgs; `UniqueConstraint(user_id, org_id)` prevents duplicates.

### Content
- **`collections`** — a knowledge base (grouping of documents) in an org.
- **`documents`** — an uploaded file or website: `source_type`, `filename`, `url`,
  `storage_key` (location in MinIO), `content_hash` (dedup), `status`, `error_msg`,
  `doc_metadata` (JSONB).
- **`chunks`** — a piece of a document's text: `content`, `chunk_index`,
  `chunk_metadata` (JSONB), `qdrant_point_id`. **Text lives in Postgres; the AI vector
  lives in Qdrant; `qdrant_point_id` links them.**

### Chat
- **`conversations`** — a chat session.
- **`messages`** — `role` (user/assistant), `content`, `cited_chunk_ids` (JSONB) — the
  chunks that backed an answer (this is how citations work).
- **`feedback`** — thumbs up/down on a message.

---

## Design decisions ("the little things")

1. **`org_id` on every content/chat table** — the multi-tenancy backbone. Every query
   filters by it, so org A can never see org B's data.
2. **Foreign keys with deliberate delete behavior:**
   - `document → chunks`: **CASCADE** (delete doc → chunks vanish, no orphans)
   - `org → everything`: **CASCADE** (delete org → wipe its data)
   - `document → collection`: **SET NULL** (delete collection → docs survive, uncategorized)
   - `* → created_by user`: **SET NULL** (delete user → their docs remain, author null)

   Rule of thumb: **CASCADE** for owned data, **SET NULL** for references.
3. **Indexes** on every column we filter by (all `org_id`s, foreign keys,
   `documents.status`, `documents.content_hash`, `chunks.qdrant_point_id`) — makes
   lookups instant instead of full-table scans.
4. **JSONB** for `doc_metadata`/`chunk_metadata`/`cited_chunk_ids` — flexible structured
   data (a PDF has pages, a website a URL, Excel has sheets) without a rigid column for
   each case; Postgres can still query inside it.
5. **`nullable`** chosen per column: required (e.g. `org_id`) vs optional (e.g. `filename`
   is null for a website, `url` is null for a file).
6. **String lengths** sized to real data (`email` 320, `content_hash` 64, `role` 20).

---

## How Alembic works

`alembic/env.py` is the bridge:

```python
config.set_main_option("sqlalchemy.url", settings.database_url)  # WHICH database
import app.models                                                 # WHAT the models are
target_metadata = Base.metadata
```

- DB URL comes from `config.py` (single source of truth — no duplicated password).
- `import app.models` registers all 9 tables onto `Base.metadata` (the "desired state").
- `compare_type=True` lets future migrations detect column-type changes.

The initial migration (`910f929fd87a_initial_schema.py`) has:
- `revision` / `down_revision` — a linked list that defines migration **order**
  (`down_revision = None` means it's the first).
- `upgrade()` — creates the tables.
- `downgrade()` — drops them in reverse (respecting foreign keys).

`alembic upgrade head` runs the needed migrations and **stamps** the version into the
`alembic_version` table, so re-running is a safe no-op. This is what makes the schema
reproducible everywhere.

---

# Setup for collaborators

Follow this to get the database schema running locally after cloning the repo.

### Prerequisites (Steps 0–3)

1. **Tools installed:** Docker Desktop (running), Python 3.11+.
2. **Repo cloned** and on the right branch:
   ```powershell
   git fetch origin
   git checkout feature/backend-scaffold-and-infra
   ```
3. **Infrastructure running** (Postgres must be up for migrations):
   ```powershell
   cd backend
   copy .env.example .env      # first time only; fill values as needed
   docker compose up -d
   docker compose ps           # postgres should be "healthy"
   ```
4. **Python env + deps:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1        # Windows PowerShell
   # source .venv/bin/activate          # macOS / Linux
   pip install -r requirements.txt
   ```

### Apply the schema

From `backend/` (with the venv active and Postgres healthy):

```powershell
alembic upgrade head
```

That creates all 9 tables. The migration file is already committed — you are just
applying it.

### Verify

```powershell
alembic current
# expected: 910f929fd87a (head)

docker exec rag-postgres psql -U rag -d rag -c "\dt"
# expected: 9 app tables + alembic_version
```

---

## Working with migrations (day-to-day)

Run all commands from `backend/` with the venv active.

| Task | Command |
|------|---------|
| Apply all pending migrations | `alembic upgrade head` |
| See current DB version | `alembic current` |
| See full history | `alembic history` |
| **After changing a model**, create a migration | `alembic revision --autogenerate -m "what changed"` |
| Roll back the last migration | `alembic downgrade -1` |
| Roll back everything | `alembic downgrade base` |

> **Important workflow:** when you change a model, you must (1) `--autogenerate` a new
> migration, (2) review the generated file, then (3) `alembic upgrade head`. Commit the
> new migration file so teammates get the same change. Never edit a migration that's
> already been pushed/applied — create a new one.

---

## Troubleshooting

| Problem | Cause / Fix |
|---------|-------------|
| `ModuleNotFoundError: app` | Run Alembic from the `backend/` folder (it adds `.` to the path via `prepend_sys_path`). |
| `connection refused` / can't reach DB | Postgres container isn't up: `docker compose up -d`, then `docker compose ps`. |
| `Target database is not up to date` | Run `alembic upgrade head` before generating a new migration. |
| Autogenerate produced an empty migration | Your models already match the DB — nothing to change. |
| Wrong DB / credentials | Check `backend/.env`; `config.py` builds `database_url` from it. |

---

## Reference

- Migration file: `backend/alembic/versions/910f929fd87a_initial_schema.py`
- Models: `backend/app/models/`
- Alembic config: `backend/alembic.ini`, `backend/alembic/env.py`
- Overall plan & decisions: [`../PLAN.md`](../PLAN.md)
- Build checklist: [`CHECKLIST.md`](CHECKLIST.md)
