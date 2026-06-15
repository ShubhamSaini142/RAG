# Step 5 — Authentication & Multi-Tenancy

This document explains the auth layer (what, why, how), how a collaborator sets it
up after cloning, and the git workflow for committing and pushing to **UAT**.

- **Explanation** → understand the design.
- [Setup for collaborators](#setup-for-collaborators) → run & test it locally.
- [Git workflow (commit & push to UAT)](#git-workflow--commit--push-to-uat).

---

## What this step delivers

Users can **register**, **log in**, and receive a **JWT** they send on every request.
Each request is scoped to the user's **organization (tenant)** and **role**, and one
org can never read or mutate another org's data.

Endpoints added:

| Method & path | Auth | What it does |
|---|---|---|
| `POST /auth/register` | public | Create user + their first org (they become `owner`); returns a token |
| `POST /auth/login` | public | Verify password; returns a token |
| `GET /auth/me` | bearer | Current user + the orgs they belong to (with role) |
| `GET /orgs` | bearer | List the caller's orgs |
| `POST /orgs` | bearer | Create a new org (caller becomes `owner`) |
| `POST /orgs/invite` | owner/admin | Add an existing user to the caller's active org |

---

## Files

| File | Purpose |
|------|---------|
| `app/auth/security.py` | bcrypt password hashing + JWT create/verify |
| `app/auth/schemas.py` | Pydantic request/response models |
| `app/auth/deps.py` | `get_current_user`, `get_current_context` (org+role), `require_role` |
| `app/api/auth.py` | register, login, me |
| `app/api/orgs.py` | list/create org, invite member |
| `tests/test_auth.py` | end-to-end test (incl. cross-org isolation) |
| `app/main.py` | wires the auth + orgs routers |

---

## Core concepts (the *why* and *how*)

### 1. Password hashing (never store the real password)
On register we store a **bcrypt hash** of the password, not the password itself. On
login we hash the input and compare. Even if the database leaks, passwords aren't
exposed. (bcrypt only uses the first 72 bytes, which we handle explicitly.)

### 2. JWT tokens (stateless auth)
On login the server issues a **signed token** containing the user id (`sub`), the
active org id (`org_id`), and an expiry (`exp`). The client sends it on every request
as `Authorization: Bearer <token>`. The server verifies the signature with
`SECRET_KEY`. **Why:** no server-side sessions → the API stays stateless and scales
horizontally. The signature is what makes the claims tamper-proof — a user cannot
change their `org_id` without the secret.

### 3. Multi-tenancy (the dependency that enforces it)
`get_current_context` reads the token, loads the user, and **verifies they're actually
a member of the org in the token** before handing the endpoint a `(user, org_id, role)`
context. Every protected query then filters by that `org_id`, so org A can't see org
B's rows. This logic lives in one place (`deps.py`) instead of being copy-pasted.

### 4. Roles (RBAC)
Each membership has a role: `owner` > `admin` > `editor` > `viewer`. `require_role(...)`
is a dependency that rejects callers without the needed role.

### Flow
```
register → creates user + org (owner) → returns token
login    → checks password           → returns token
          client stores token, sends "Authorization: Bearer <token>"
me / orgs / future endpoints → require a valid token, scoped to the org
```

---

## Security hardening (from the adversarial review)

This step was put through an adversarial security review; four issues were found and fixed:

| Severity | Issue | Fix |
|----------|-------|-----|
| 🔴 Critical | Default `SECRET_KEY` would allow forged tokens | App refuses to boot outside `development` if the secret is default/weak (`config.py` validator) |
| 🟠 High | An admin could invite a member as `owner` (privilege escalation) | Role-ceiling check — you can't grant a role higher than your own |
| 🟡 Medium | Oversized `name`/`org_name` caused a 500 | `max_length=255` on inputs + clamp of the derived org name |
| 🔵 Low | Login response time revealed which emails exist | Always run bcrypt (against a dummy hash) even when the email is unknown |

> **Production note:** set a strong `SECRET_KEY` and `APP_ENV=production` in `.env`.
> Generate a secret with:
> ```bash
> python -c "import secrets; print(secrets.token_urlsafe(64))"
> ```

---

# Setup for collaborators

After cloning and getting Steps 0–4 done (infra running + DB migrated), Step 5 needs
no special setup beyond installing deps — the code is already in the repo.

1. **Infra + DB ready** (see `step-04-database-schema.md`):
   ```powershell
   cd backend
   docker compose up -d
   alembic upgrade head
   ```
2. **Install deps** (Step 5 added `email-validator`):
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Run the API:**
   ```powershell
   uvicorn app.main:app --reload
   ```

### Try it
Open the interactive API docs at **http://localhost:8000/docs** — you can call
`register`/`login`, copy the returned token, click **Authorize**, and hit the
protected endpoints. Or with `curl`:

```bash
# Register (returns access_token + org_id)
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"password123","name":"Alice"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"password123"}'

# Call a protected endpoint (paste the token)
curl http://localhost:8000/auth/me -H "Authorization: Bearer <TOKEN>"
```

> On Windows PowerShell, `curl` is an alias for `Invoke-WebRequest` (different syntax);
> use `curl.exe ...` or just use the `/docs` UI.

### Run the test
```powershell
# from backend/, venv active
python -m tests.test_auth
# expected: OK - all auth flow assertions passed
```
The test covers register, duplicate rejection, wrong/right password, `/me`,
**cross-org isolation**, invite, oversized input, and bad tokens.

---

# Git workflow — commit & push to UAT

The shared integration branch is **`UAT`**. The standard flow:

```powershell
# 1. Start from up-to-date UAT
git checkout UAT
git pull origin UAT

# 2. Branch for your work
git checkout -b feature/<short-description>

# 3. Make changes, then stage + commit
git add -A
git status                      # confirm no .env / secrets are staged
git commit -m "Step 5: short description of the change"

# 4. Push your branch
git push -u origin feature/<short-description>

# 5. Merge into UAT — either open a Pull Request on GitHub (preferred for review),
#    or merge locally:
git checkout UAT
git merge feature/<short-description>
git push origin UAT
```

**Rules:**
- Never commit the real `.env` (it's git-ignored; only `.env.example` is shared).
- Commit the Alembic migration file whenever you change a model.
- Keep secrets (API keys, tokens) out of code and commits.

---

## Reference
- Models & DB: [`step-04-database-schema.md`](step-04-database-schema.md)
- Plan & decisions: [`../PLAN.md`](../PLAN.md)
- Build checklist: [`CHECKLIST.md`](CHECKLIST.md)
- Code: `backend/app/auth/`, `backend/app/api/auth.py`, `backend/app/api/orgs.py`
