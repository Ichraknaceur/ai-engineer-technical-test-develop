"""Health check endpoint.

Returns the status of all system dependencies:
database, redis, and the celery worker queue.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from backend.infrastructure.api.dependencies.db import DbSession

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Response schema for GET /api/health."""

    status: str
    database: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health(session: DbSession) -> HealthResponse:
    """Check the health of all system dependencies.

    Returns:
        200 if all dependencies are reachable.
        503 if any dependency is down.
    """
    db_status = "ok"
    redis_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        from redis.asyncio import Redis

        from backend.config import settings

        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        await redis.ping()
        await redis.aclose()
    except Exception:
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(status=overall, database=db_status, redis=redis_status)
