# Step 9 — Usage analytics + token tracking

Every chat answer now records **token usage**, and there's a dashboard for it: a user
sees **their own** usage; an **owner/admin** sees the **whole organization** (including a
per-user breakdown). Backend captures the numbers; the frontend renders stat tiles +
charts.

- **Explanation** → understand what's tracked and how.
- [Setup for collaborators](#setup-for-collaborators).
- [Git workflow](#git-workflow--commit--push-to-uat).

---

## What this step delivers

- A per-request **`usage_events`** table (append-only, tenant-scoped): org, user,
  conversation, provider, model, and input/output/total tokens.
- **Token capture** from streamed LLM responses — read from LangChain's
  `usage_metadata`, so it works across OpenAI / Anthropic / Gemini / OpenAI-compatible.
- Two endpoints:
  - **`GET /analytics/me`** — the caller's own usage.
  - **`GET /analytics/org`** — org-wide usage + **per-user breakdown** (owner/admin only).
- A **frontend dashboard** (`/analytics`): stat tiles (total tokens, requests, documents,
  conversations), a **tokens-over-time** area chart (input vs. output), **tokens by
  model**, and — for admins — **tokens by user**. Admins get a scope toggle
  (Organization ↔ Just me).

## How token capture works (the *why* and *how*)

### Reading usage off a stream
For a streamed answer, providers emit token counts on the **final chunk**. The
`LangChainLLMProvider` adapter accumulates chunks (`full = full + chunk`) and, when the
stream finishes, reads `full.usage_metadata` into `self.last_usage`
(`{input_tokens, output_tokens, total_tokens}`). OpenAI needs `stream_usage=True` (set in
the builders); Anthropic and Gemini include usage by default. Some local
OpenAI-compatible servers don't report usage — those record `0` (the request still
counts).

### Recording without slowing chat down
After the answer is persisted, `chat.py` calls `record_chat_usage(...)` in a threadpool
inside the stream's `finally`. It's **best-effort**: a failure is logged and swallowed,
never breaking the chat response. The provider/model labels come from the org's
`provider_settings`.

### Aggregation + scoping
`analytics/service.py::summary(db, org_id, user_id)` builds everything from
`usage_events`:
- **Totals** (sum of tokens, request count) + **documents** and **conversations** counts.
- **Daily series** over the trailing 30 days (`date_trunc('day', …)`).
- **By provider/model**.
- **By user** (org scope only, via an outer join to `users`).

Pass `user_id` for the personal view; pass `None` for the org-wide view. `/analytics/org`
is gated by `require_role("owner", "admin")`, so a viewer/editor can only ever see their
own numbers.

## Charts & color (frontend)

Charts use **Recharts**, themed with the app's tokens (theme-aware axes/grid/tooltips).
The categorical series colors (input = blue, output = aqua) were **validated for
color-vision-deficiency and contrast** with the data-viz validator before use (worst
adjacent CVD ΔE ≈ 70, well above the ≥ 12 target). Identity is never color-alone: every
chart has a **legend** and tooltips label each series. Number formatting is compact
(`1.2k`, `3.4M`).

---

## Files

| Area | Files |
|------|-------|
| Model | `app/models/usage.py` (`UsageEvent`) + migration `a1b2c3d4e5f6` |
| Capture | `app/providers/langchain_adapters.py` (`last_usage`), `openai*_provider.py` (`stream_usage=True`), `app/api/chat.py` |
| Service | `app/analytics/service.py` (`record_chat_usage`, `summary`) |
| API | `app/api/analytics.py` (`/analytics/me`, `/analytics/org`) |
| Frontend | `frontend/src/app/(app)/analytics/page.tsx`, `components/ui/stat.tsx`, chart tokens in `globals.css` |
| Test | `backend/tests/test_analytics.py` |

## API shape

`GET /analytics/me` / `GET /analytics/org`:
```json
{
  "scope": "org",
  "totals": { "input_tokens": 1240, "output_tokens": 860, "total_tokens": 2100,
              "requests": 42, "documents": 7, "conversations": 12 },
  "daily":  [ { "date": "2026-07-05", "input_tokens": 120, "output_tokens": 80,
                "total_tokens": 200, "requests": 4 } ],
  "by_model": [ { "provider": "openai", "model": "gpt-4o-mini",
                  "total_tokens": 2100, "requests": 42 } ],
  "by_user":  [ { "user_id": "…", "email": "you@example.com", "name": "You",
                  "total_tokens": 2100, "requests": 42 } ]
}
```
`by_user` is present only for `/analytics/org`. See [api-reference.md](api-reference.md).

---

# Setup for collaborators

Prereqs: Steps 0–8 done. Then:

1. **Apply the migration** (adds `usage_events`):
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   alembic upgrade head
   ```
2. **Run API + worker**, configure a provider, and **ask a question or two** in Chat.
3. Open **http://localhost:3000/analytics** — your usage appears. As an owner/admin,
   toggle to **Organization** for the org-wide view + per-user breakdown.

### Run the test (no real provider key needed)
```powershell
python -m tests.test_analytics   # records usage via a fake LLM, checks aggregation + scoping + isolation
```

---

# Git workflow — commit & push to UAT

```powershell
git checkout UAT
git pull origin UAT
git checkout -b feature/analytics
git add -A
git status                 # confirm no .env / secrets staged
git commit -m "Step 9: usage analytics + token tracking"
git push -u origin feature/analytics
# open a PR to UAT, or merge locally and: git push origin UAT
```
Commit the new migration (`a1b2c3d4e5f6`).

## Known limitations / next
- Only **chat LLM** tokens are tracked; embedding-token usage on ingestion is not yet
  recorded (providers vary in reporting it).
- No cost estimate (would need per-model price tables) or CSV export yet.
- No date-range filter on the dashboard (fixed 30-day window); add presets later.

## Reference
- Frontend: [`step-08-frontend.md`](step-08-frontend.md) · BYOK: [`step-07-byok-providers.md`](step-07-byok-providers.md)
- Plan: [`../PLAN.md`](../PLAN.md) · Checklist: [`CHECKLIST.md`](CHECKLIST.md)
