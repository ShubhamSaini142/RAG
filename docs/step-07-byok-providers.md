# Step 7 — Bring-Your-Own-Key (BYOK) + Multi-Provider

Each **organization** configures its **own** LLM and embedding provider + API key.
Keys are **encrypted at rest** (never in env, never returned in plaintext), and
chat/ingest is **disabled until a provider is configured**. No single-vendor lock-in.

- **Explanation** → understand the design.
- [Setup for collaborators](#setup-for-collaborators) → run it + configure a provider.
- [Git workflow](#git-workflow--commit--push-to-uat).

---

## What this step delivers

- A per-org **`provider_settings`** table (one row per `kind` = `llm` | `embedding`),
  with the API key stored **Fernet-encrypted**.
- **Tenant-aware factories** `get_llm_provider(org_id, db)` / `get_embedding_provider(org_id, db)`
  that load the org's config, decrypt the key, and return a ready provider.
- **Multi-provider** LLMs: OpenAI, Anthropic (Claude), Google Gemini, and any
  **OpenAI-compatible** endpoint (Ollama / vLLM / OpenRouter via `base_url`).
- **Per-org Qdrant collections** (`org_<id>`) so each org's embedding model/dimension
  is isolated.
- **Settings API** to configure providers, with the embedding **dimension auto-detected**.
- **Require-key gating**: upload/chat return `409` until the org configures providers.

## Two hard constraints this design handles
1. **Anthropic (Claude) has no embeddings API** → "provider" is split into a separate
   **LLM** config and **embedding** config. A Claude org must pick a different embedding
   provider (OpenAI / Gemini / local).
2. **Full BYO embeddings → different vector dimensions** → we can't share one Qdrant
   collection. Each org gets its own, sized to its embedding model. **Changing an org's
   embedding model requires re-indexing** (the dimension/space changes).

---

## Files

| Area | Files |
|------|-------|
| Encryption | `app/crypto.py` (Fernet encrypt/decrypt/mask), `ENCRYPTION_KEY` in config/.env |
| Model | `app/models/provider_settings.py` + migration `c6b305320af5` |
| Providers | `app/providers/__init__.py` (org-aware factories); `registry.py` (redirector); one module per provider: `openai_provider.py`, `anthropic_provider.py`, `gemini_provider.py`, `openai_compatible_provider.py`; `langchain_adapters.py` |
| Vector store | `app/vectorstore/qdrant_store.py` (`org_collection`, per-org, dim-aware) |
| Settings API | `app/api/settings.py` |
| Wiring/gating | `app/api/documents.py`, `app/api/chat.py`, `app/ingestion/tasks.py` |
| Tests | `tests/test_providers.py`, updated `tests/test_rag.py` |

---

## Core concepts (the *why* and *how*)

### Encryption at rest
`ENCRYPTION_KEY` (a Fernet key) is the **only** secret in env — provider keys never
are. On save, the key is `encrypt()`-ed before it touches Postgres; it's `decrypt()`-ed
only when a request actually calls the provider. API responses return a **masked**
form (`••••last4`) — plaintext is never echoed.

### Tenant-aware provider resolution
The factories look up `provider_settings` for the request's `org_id` (from the JWT),
decrypt the key, and build the provider via the **registry** (one branch per provider,
lazily importing its LangChain integration). Add a provider = add a branch; nothing
else changes.

### Per-org Qdrant collections
Collection name is `org_<org_id>`, created with that org's embedding **dimension** when
the first document is ingested. The `org_id` payload filter is kept as defense-in-depth.

### Require-key gating
`POST /documents` → `409` if no embedding provider configured. `POST /chat` → `409` if
embedding or LLM provider missing. So an org only ever spends **its own** quota.

### Embedding dimension auto-detect
On `PUT /settings/providers/embedding`, a one-shot probe embeds a test string; the
vector length becomes the stored `embedding_dim` (and the probe validates the key).
Changing the embedding model while documents exist is **blocked** (dimensions differ).

---

## Configure a provider (API)

`PUT /settings/providers/embedding` (owner/admin):
```json
{ "provider": "openai", "model": "text-embedding-3-small", "api_key": "sk-..." }
```
`PUT /settings/providers/llm` (owner/admin):
```json
{ "provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-ant-..." }
```
Examples per provider:
| provider | LLM model e.g. | embedding model e.g. | notes |
|----------|----------------|----------------------|-------|
| `openai` | `gpt-4o-mini` | `text-embedding-3-small` | |
| `anthropic` | `claude-sonnet-4-6` | — (no embeddings) | use OpenAI/Gemini for embeddings |
| `gemini` | `gemini-1.5-flash` | `text-embedding-004` | |
| `openai_compatible` | any | any | requires `base_url` (Ollama/vLLM/OpenRouter) |

`GET /settings/providers` returns both configs with **masked** keys.

---

## Hardening (from the adversarial review)

| Severity | Issue | Fix |
|----------|-------|-----|
| 🟠 High | Provider validation errors echoed the raw exception (could reflect the key/base_url) | Generic error messages; full detail logged server-side with the key redacted |
| 🟠 High | Ingestion stored the raw provider exception in `Document.error_msg` (served via API) | Sanitized category message for the API; full detail in server logs only |
| 🟠 High | Embedding-change guard keyed off provider/model strings → a `base_url`/dim swap could desync the index | Guard on the **probed dimension** vs stored `embedding_dim`; `ensure_collection` rejects a dim mismatch; deterministic collection drop on change |
| 🟠 High | `ENCRYPTION_KEY` wasn't validated at boot (prod could start without it) | Boot validation: outside dev, require a valid Fernet key (fail closed) |
| 🟡 Medium | `GET /providers` decrypted the real key on every read to re-mask it | Store a non-reversible `api_key_hint` at write time; reads never decrypt |
| 🔵 Low | `openai_compatible` `base_url` unvalidated | Require a valid `http(s)` URL |
| 🔵 Low | `mask()` over-revealed short secrets | Hide entirely below 12 chars |

---

# Setup for collaborators

Prereqs: Steps 0–6 done (infra up, deps installed). Then:

1. **Install the new deps** (Step 7 added them) + set an encryption key:
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt        # cryptography, langchain-anthropic, langchain-google-genai
   # add ENCRYPTION_KEY to backend/.env:
   python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
   ```
2. **Apply the migration:** `alembic upgrade head`
3. **Run API + worker** (worker needed for ingest):
   ```powershell
   uvicorn app.main:app --reload
   celery -A app.celery_app worker --loglevel=info --pool=solo   # separate terminal
   ```
4. **Configure your provider** in Swagger (`/docs`): register → Authorize → `PUT
   /settings/providers/embedding` + `/llm` with your own key → then upload + chat.

### Run the tests (no real provider key needed)
```powershell
python -m tests.test_providers   # encryption-at-rest, dim auto-detect, masked GET
python -m tests.test_rag         # require-key gate -> configure -> ingest -> cited answer -> isolation
python -m tests.test_auth        # auth + multi-tenant isolation
```
Tests patch the provider registry/factories with fakes, so they validate the full flow
without calling OpenAI/Anthropic/Gemini.

---

# Git workflow — commit & push to UAT

```powershell
git checkout UAT
git pull origin UAT
git checkout -b feature/<short-description>
git add -A
git status                 # confirm no .env / secrets staged
git commit -m "Step 7: short description"
git push -u origin feature/<short-description>
# open a PR to UAT, or merge locally and: git push origin UAT
```
Never commit the real `.env` (it holds `ENCRYPTION_KEY`); commit new Alembic migrations.

---

## Known limitations / next
- Changing an org's embedding model requires deleting docs first (auto re-index later).
- Embedding providers: OpenAI / Gemini / OpenAI-compatible (Anthropic has no embeddings).
- LLM key is validated on first use; embedding key is validated at save (dim probe).
- Per-request provider/clients are built fresh — fine for MVP; pool/cache later.

## Reference
- RAG slice: [`step-06-rag-slice.md`](step-06-rag-slice.md) · Auth: [`step-05-auth.md`](step-05-auth.md)
- Plan: [`../PLAN.md`](../PLAN.md) · Checklist: [`CHECKLIST.md`](CHECKLIST.md)
