"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health

app = FastAPI(title="RAG Knowledge Base API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)

# Future routers (added in later milestones):
# app.include_router(auth.router)
# app.include_router(orgs.router)
# app.include_router(collections.router)
# app.include_router(documents.router)
# app.include_router(chat.router)
# app.include_router(feedback.router)


@app.get("/")
def root() -> dict:
    return {"service": "rag-backend", "status": "ok"}
