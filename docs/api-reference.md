# API Reference

Complete reference for the RAG Knowledge Base API — every endpoint with request
shape, a copy-paste `curl`, an example response, and the steps to use it.

> **Interactive docs:** the API also serves live Swagger UI at **`/docs`** and the
> raw spec at **`/openapi.json`**. The examples below use `curl` against a local
> server.

---

## Contents
1. [Basics](#basics) — base URL, auth, errors
2. [Quick start](#quick-start) — the end-to-end flow
3. [Health](#health)
4. [Auth](#auth)
5. [Organizations](#organizations)
6. [Settings — AI providers (BYOK)](#settings--ai-providers-byok)
7. [Documents](#documents)
8. [Chat](#chat)
9. [Status codes](#status-codes)

---

## Basics

| | |
|---|---|
| **Base URL** | `http://localhost:8000` |
| **Auth** | JWT bearer token. Send `Authorization: Bearer <access_token>` on every protected call. |
| **Content type** | `application/json` (except file upload, which is `multipart/form-data`). |
| **Tenancy** | All data is scoped to your **organization**; the org is taken from your token, never the request body. |

**Error shape** — failures return a JSON body:
```json
{ "detail": "Human-readable message" }
```

> **Windows note:** in PowerShell, `curl` is an alias for `Invoke-WebRequest` (different
> syntax). Use `curl.exe` for the examples below, or just use the `/docs` UI.

---

## Quick start

The happy path, in order. Each step links to its endpoint below.

```
1. POST /auth/register                 -> get access_token (+ your org)
2. PUT  /settings/providers/embedding  -> configure embeddings (BYOK)
3. PUT  /settings/providers/llm        -> configure the chat LLM (BYOK)
4. POST /documents                     -> upload a .txt/.md file
5. GET  /documents/{id}                -> poll until status == "ready"
6. POST /chat                          -> ask a question (streamed, cited answer)
```
Steps 2–3 are required: uploads and chat return **409** until providers are configured.

---

## Health

### `GET /health` — service + dependency health
Checks the API can reach Postgres and Qdrant. No auth.

```bash
curl http://localhost:8000/health
```
```json
{ "status": "ok", "checks": { "postgres": "ok", "qdrant": "ok" } }
```

### `GET /` — service banner
```bash
curl http://localhost:8000/
```
```json
{ "service": "rag-backend", "status": "ok", "docs": "/docs" }
```

---

## Auth

### `POST /auth/register` — create a user + organization
Creates the user, creates their first organization (they become `owner`), and returns a token.

**Body**

| field | type | required | notes |
|-------|------|----------|-------|
| `email` | string | ✓ | must be unique |
| `password` | string | ✓ | 8–128 chars |
| `name` | string | | ≤ 255 chars |
| `org_name` | string | | defaults to `"<name>'s Organization"` |

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"password123","name":"Alice"}'
```
```json
{ "access_token": "eyJhbGci...", "token_type": "bearer", "org_id": "f1e2..." }
```
**Steps:** save the `access_token`; send it as `Authorization: Bearer <token>` on every call below.

### `POST /auth/login` — exchange credentials for a token
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"password123"}'
```
```json
{ "access_token": "eyJhbGci...", "token_type": "bearer", "org_id": "f1e2..." }
```
`401` on a wrong email or password (same message either way).

### `GET /auth/me` — current user + organizations
```bash
curl http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
```
```json
{
  "user": { "id": "a1b2...", "email": "alice@example.com", "name": "Alice" },
  "orgs": [ { "id": "f1e2...", "name": "Alice's Organization", "plan": "free", "role": "owner" } ]
}
```

---

## Organizations

### `GET /orgs` — list your organizations
```bash
curl http://localhost:8000/orgs -H "Authorization: Bearer $TOKEN"
```
```json
[ { "id": "f1e2...", "name": "Alice's Organization", "plan": "free", "role": "owner" } ]
```

### `POST /orgs` — create a new organization
You become its `owner`.
```bash
curl -X POST http://localhost:8000/orgs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp"}'
```
```json
{ "id": "99aa...", "name": "Acme Corp", "plan": "free", "role": "owner" }
```

### `POST /orgs/invite` — add a member to your active org
**Role:** `owner` or `admin`. You cannot grant a role higher than your own. The invited
user must already be registered.

**Body:** `{ "email": "bob@example.com", "role": "viewer" }` — `role` ∈ `owner|admin|editor|viewer` (default `viewer`).

```bash
curl -X POST http://localhost:8000/orgs/invite \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email":"bob@example.com","role":"editor"}'
```
`404` if no user with that email · `409` if already a member · `403` if granting above your role.

---

## Settings — AI providers (BYOK)

Configure your organization's **own** LLM and embedding provider + API key. Keys are
stored **encrypted**; responses show only a masked hint. **Required before upload/chat.**

| provider | LLM model e.g. | embedding model e.g. | notes |
|----------|----------------|----------------------|-------|
| `openai` | `gpt-4o-mini` | `text-embedding-3-small` | |
| `anthropic` | `claude-sonnet-4-6` | — | no embeddings; pick another embedder |
| `gemini` | `gemini-1.5-flash` | `text-embedding-004` | |
| `openai_compatible` | any | any | requires `base_url` (Ollama/vLLM/OpenRouter) |

### `GET /settings/providers` — view current config (masked)
```bash
curl http://localhost:8000/settings/providers -H "Authorization: Bearer $TOKEN"
```
```json
{
  "llm": { "kind": "llm", "provider": "anthropic", "model": "claude-sonnet-4-6",
           "base_url": null, "embedding_dim": null, "api_key_masked": "••••7a1c", "configured": true },
  "embedding": { "kind": "embedding", "provider": "openai", "model": "text-embedding-3-small",
                 "base_url": null, "embedding_dim": 1536, "api_key_masked": "••••9f2b", "configured": true }
}
```

### `PUT /settings/providers/embedding` — set the embedding provider
**Role:** `owner`/`admin`. A live probe validates the key and **auto-detects** the vector dimension.

**Body:** `{ "provider": "openai", "model": "text-embedding-3-small", "api_key": "sk-...", "base_url": null }`
```bash
curl -X PUT http://localhost:8000/settings/providers/embedding \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"provider":"openai","model":"text-embedding-3-small","api_key":"sk-..."}'
```
```json
{ "kind": "embedding", "provider": "openai", "model": "text-embedding-3-small",
  "base_url": null, "embedding_dim": 1536, "api_key_masked": "••••...", "configured": true }
```
`400` if the key/provider can't be validated. Changing to a model with a **different
dimension** while documents exist returns `409` (delete documents first).

### `PUT /settings/providers/llm` — set the chat LLM provider
**Role:** `owner`/`admin`.

**Body:** `{ "provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-ant-...", "base_url": null }`
```bash
curl -X PUT http://localhost:8000/settings/providers/llm \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"provider":"anthropic","model":"claude-sonnet-4-6","api_key":"sk-ant-..."}'
```
`422` if `provider=openai_compatible` without a valid `base_url`.

---

## Documents

### `POST /documents` — upload a document
**Auth:** any member. `multipart/form-data` with a `file` field. Supported: `.txt`, `.md`
(more types coming). Max 10 MB. Indexed asynchronously — poll status until `ready`.

```bash
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@notes.txt;type=text/plain"
```
```json
{ "id": "d4c3...", "filename": "notes.txt", "source_type": "txt", "status": "queued", "error_msg": null }
```
`409` if no embedding provider configured · `400` unsupported type / empty · `413` too large.
**Steps:** then `GET /documents/{id}` until `status` is `ready` (or `failed`).

### `GET /documents` — list your documents
```bash
curl http://localhost:8000/documents -H "Authorization: Bearer $TOKEN"
```
```json
[ { "id": "d4c3...", "filename": "notes.txt", "source_type": "txt", "status": "ready", "error_msg": null } ]
```

### `GET /documents/{document_id}` — get one document (status)
```bash
curl http://localhost:8000/documents/d4c3... -H "Authorization: Bearer $TOKEN"
```
`status` ∈ `queued | processing | ready | failed`. `404` if not in your org.

### `DELETE /documents/{document_id}` — delete a document
Removes the file, its chunks (Postgres), and its vectors (Qdrant). Returns `204`.
```bash
curl -X DELETE http://localhost:8000/documents/d4c3... -H "Authorization: Bearer $TOKEN"
```

---

## Chat

### `POST /chat` — ask a question (streamed, cited answer)
**Auth:** any member. Requires both providers configured (else `409`). Returns a
**Server-Sent Events** stream.

**Body**

| field | type | default | notes |
|-------|------|---------|-------|
| `question` | string | — | 1–4000 chars |
| `collection_id` | uuid | null | restrict to one collection |
| `conversation_id` | uuid | null | continue an existing conversation |
| `top_k` | int | 5 | 1–20 chunks to retrieve |

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"What does the document say about pricing?"}'
```
**Response** (`text/event-stream`): a `citations` event first, then `token` events with
answer text, then a final `done` event.
```
event: citations
data: [{"n":1,"chunk_id":"...","document_id":"d4c3...","snippet":"...","score":0.82}]

event: token
data: {"text": "Based "}

event: token
data: {"text": "on the context, ... [1]"}

event: done
data: {"conversation_id": "c0ff..."}
```
**Steps:** read `citations` for sources, concatenate `token` texts for the answer, and
keep `conversation_id` from `done` to continue the thread. With no relevant context the
`citations` array is empty and the model answers "I don't know".

---

## Status codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created (register, create org, upload, set provider) |
| `204` | Deleted (no body) |
| `400` | Bad input (unsupported file, empty file, unvalidatable provider key) |
| `401` | Missing/invalid token, or wrong login |
| `403` | Authenticated but not allowed (role too low, not a member of the org) |
| `404` | Not found / not in your org |
| `409` | Conflict (email taken, already a member, **provider not configured**, embedding-dim change with docs) |
| `413` | Upload too large (> 10 MB) |
| `422` | Validation error (malformed body, missing `base_url` for openai_compatible) |
| `503` | Vector store temporarily unavailable |

---

## See also
- [step-05-auth.md](step-05-auth.md) — auth & roles
- [step-06-rag-slice.md](step-06-rag-slice.md) — ingestion → chat pipeline
- [step-07-byok-providers.md](step-07-byok-providers.md) — provider configuration
