# Step 8 — Frontend (Next.js UI)

A **Next.js** web app over the existing FastAPI backend: register/sign in, configure
your own model keys, upload documents, and ask questions with **streamed, cited
answers** — plus an analytics dashboard ([step-09](step-09-analytics.md)). Built with a
small **design system** (semantic tokens, light/dark) so the look is consistent and
easy to restyle.

- **Explanation** → understand the architecture and the key decisions.
- [Setup for collaborators](#setup-for-collaborators) → run it locally.
- [Git workflow](#git-workflow--commit--push-to-uat).

---

## What this step delivers

- A **Next.js 16** app (App Router, TypeScript, **Tailwind v4**) in `frontend/`.
- **Design system**: semantic CSS-variable tokens (`background`, `card`, `primary`,
  `muted`, `destructive`, …), light/dark theme with **no flash**, and reusable
  primitives (`Button`, `Input`, `Card`, `Badge`, `Toast`, …).
- **Typed API client** (`lib/api.ts`) with a JWT stored client-side and injected as
  `Authorization: Bearer`; any `401` clears the token and bounces to `/login`.
- **Auth**: register / login pages + a protected route group guarded by an auth context.
- **App shell**: sidebar nav (Chat · Documents · Analytics · Settings), topbar with the
  active org/role, a theme toggle, and sign-out.
- **Settings (BYOK)**: forms to set the embedding + chat providers; keys shown only as
  masked hints; friendly `409` ("configure a provider first") handling.
- **Documents**: drag-and-drop upload, a list with **live status polling**
  (queued → processing → ready/failed), and delete.
- **Chat**: a composer + message thread that consumes the backend **SSE** stream token
  by token, renders **citations**, and keeps the `conversation_id` for follow-ups.

## Architecture & key decisions (the *why*)

### Client-rendered SPA over the API
The app is a token-authenticated dashboard, not public SEO content, so pages are
**client components** (`"use client"`) that call the API directly. This keeps auth
simple (the JWT lives in the browser) and avoids server-side data fetching / the async
`params`/`cookies` machinery. The root and the protected group redirect based on auth
state.

### Design system first
`globals.css` defines **semantic tokens** as CSS variables in `:root` and `.dark`, then
maps them into Tailwind's color namespace via `@theme inline`. Components only ever
reference roles (`bg-card`, `text-muted-foreground`, `border-border`) — so the entire
theme (including dark mode) swaps in one place. An inline `<script>` in the root layout
applies the saved theme **before first paint** to avoid a flash.

### One API layer, one 401 rule
Every call goes through `request()` in `lib/api.ts`. It attaches the bearer token,
parses `{ "detail": … }` errors into a typed `ApiError`, and on `401` clears the token
and calls the registered unauthorized handler (the auth context redirects to `/login`).
No page repeats auth logic.

### SSE via `fetch`, not `EventSource`
Chat streams Server-Sent Events, but `EventSource` can't send an `Authorization` header
or POST a body. So `streamChat()` uses `fetch` + a `ReadableStream` reader and parses
`event:`/`data:` frames manually, invoking `onCitations` / `onToken` / `onDone`
callbacks. An `AbortController` powers the **stop** button.

### Live status without websockets
Uploads index asynchronously (Celery). The documents page **polls** `GET /documents`
every 2.5s *only while* something is `queued`/`processing`, then stops — simple, cheap,
and good enough for the MVP.

---

## Files

| Area | Files |
|------|-------|
| Theme / tokens | `src/app/globals.css`, `src/lib/theme.tsx`, `src/components/theme-toggle.tsx` |
| UI primitives | `src/components/ui/*` (`button`, `input`, `card`, `badge`, `spinner`, `toast`, `page`, `stat`) |
| API + auth | `src/lib/api.ts`, `src/lib/types.ts`, `src/lib/auth.tsx` |
| Auth pages | `src/app/login/page.tsx`, `src/app/register/page.tsx`, `src/components/auth-shell.tsx` |
| Shell + guard | `src/app/(app)/layout.tsx`, `src/components/app-shell.tsx`, `src/components/brand.tsx` |
| Features | `src/app/(app)/settings/page.tsx`, `documents/page.tsx`, `chat/page.tsx`, `analytics/page.tsx` |

## Project layout

```
frontend/
├── .env.local            # NEXT_PUBLIC_API_URL (git-ignored)
├── .env.example          # template (tracked)
└── src/
    ├── app/
    │   ├── layout.tsx     # fonts + Theme/Toast/Auth providers + no-flash script
    │   ├── page.tsx       # root → redirect to /chat or /login
    │   ├── login/ · register/
    │   └── (app)/         # protected group (auth guard in layout.tsx)
    │       ├── chat/ · documents/ · settings/ · analytics/
    ├── components/        # brand, app-shell, theme-toggle, ui/*
    └── lib/               # api, types, auth, theme, utils
```

---

# Setup for collaborators

Prereqs: **Node 18+** (Node 24 tested) and the **backend running** (see
[SETUP.md](../SETUP.md) — infra up, migrations applied, API + worker running, a provider
configured). Then:

```powershell
cd frontend
copy .env.example .env.local          # already points at http://localhost:8000
npm install
npm run dev                            # http://localhost:3000
```

Open **http://localhost:3000** → Register → you'll land on **Settings** to add your own
embedding + chat provider keys → then **Documents** (upload a `.txt`/`.md`) → **Chat**.

> If the API isn't on `localhost:8000`, set `NEXT_PUBLIC_API_URL` in `.env.local`.
> The backend already allows CORS from any origin in dev.

### Handy commands
```powershell
npm run dev        # dev server (hot reload)
npm run build      # production build (also full typecheck)
npm run lint       # eslint
npx tsc --noEmit   # typecheck only
```

---

# Git workflow — commit & push to UAT

```powershell
git checkout UAT
git pull origin UAT
git checkout -b feature/frontend
git add -A
git status                 # confirm no .env.local / secrets staged (.env.example is fine)
git commit -m "Step 8: Next.js frontend (auth, BYOK, documents, chat)"
git push -u origin feature/frontend
# open a PR to UAT, or merge locally and: git push origin UAT
```
`frontend/.gitignore` ignores `node_modules`, `.next`, and `.env*` **except**
`.env.example`. Never commit `.env.local`.

## Known limitations / next
- Token is kept in `localStorage` (fine for this app; consider httpOnly cookies for
  higher-security deployments).
- No org **switcher** yet — the app uses the org from your login token.
- Provider/client per request; no request cancellation on navigation away from chat
  besides the explicit stop button.
- Dockerizing the frontend + a compose service is deferred (run with `npm` for now).

## Reference
- API surface: [`api-reference.md`](api-reference.md) · BYOK: [`step-07-byok-providers.md`](step-07-byok-providers.md)
- Analytics UI: [`step-09-analytics.md`](step-09-analytics.md) · Plan: [`../PLAN.md`](../PLAN.md)
