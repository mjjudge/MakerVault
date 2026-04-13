"""Health check endpoint.

GET /api/health — returns service status and version.
Used by Docker healthchecks, load balancers, and smoke tests.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.config import Settings, get_settings
from makervault.database import get_db_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db_session),
) -> HealthResponse:
    """Return service health status.

    Performs a lightweight database connectivity check (``SELECT 1``).
    Returns ``database: "ok"`` when the DB is reachable, or ``"unavailable"``
    if the check fails (without raising an HTTP error, so the endpoint remains
    useful even when the DB is down).
    """
    db_status = "unavailable"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001
        pass

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        database=db_status,
    )
