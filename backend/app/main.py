"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, documents, health, orgs

DESCRIPTION = """
Multi-tenant **Retrieval-Augmented Generation** knowledge base.

Upload documents, and ask natural-language questions that are answered by an LLM
**grounded in your own content, with citations**.

### Getting started
1. **`POST /auth/register`** — creates your user + organization, returns an `access_token`.
2. Click **Authorize** (top right) and paste the token — it persists across calls.
3. **`POST /documents`** — upload a `.txt`/`.md` file (it's indexed in the background).
4. **`POST /chat`** — ask a question; the answer streams back (SSE) with citations.

All data is scoped to your organization — one org can never see another's.
"""

TAGS_METADATA = [
    {"name": "auth", "description": "Register, log in, and inspect the current user."},
    {"name": "orgs", "description": "Organizations (tenants) and membership / invites."},
    {
        "name": "documents",
        "description": "Upload and manage documents. Uploads are extracted, chunked, "
        "embedded and indexed asynchronously — poll status until `ready`.",
    },
    {
        "name": "chat",
        "description": "Ask questions; get a streamed (SSE), cited answer grounded in "
        "your documents.",
    },
    {"name": "health", "description": "Liveness/readiness — checks Postgres and Qdrant."},
]

app = FastAPI(
    title="RAG Knowledge Base API",
    description=DESCRIPTION,
    version="0.6.0",
    openapi_tags=TAGS_METADATA,
    contact={"name": "RAG Knowledge Base"},
    license_info={"name": "Proprietary"},
    swagger_ui_parameters={
        "persistAuthorization": True,  # keep the bearer token across page reloads
        "docExpansion": "none",        # collapsed, tidy endpoint list
        "filter": True,                # search box for endpoints
        "displayRequestDuration": True,
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(documents.router)
app.include_router(chat.router)

# Future routers (added in later milestones):
# app.include_router(collections.router)
# app.include_router(feedback.router)


@app.get("/", tags=["health"], summary="Service banner")
def root() -> dict:
    return {"service": "rag-backend", "status": "ok", "docs": "/docs"}
