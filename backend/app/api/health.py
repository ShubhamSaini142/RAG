"""Health check endpoint — verifies the API can reach Postgres and Qdrant."""
from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    checks: dict[str, str] = {}

    # Postgres
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {exc}"

    # Qdrant
    try:
        from qdrant_client import QdrantClient

        from app.config import settings

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["qdrant"] = f"error: {exc}"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
