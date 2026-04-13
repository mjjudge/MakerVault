"""Project suggestion API router.

Endpoints
---------
POST   /suggestions              — create and immediately run a suggestion
GET    /suggestions              — list suggestions (paginated)
GET    /suggestions/{id}         — get a single suggestion
DELETE /suggestions/{id}         — delete a suggestion record
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.project_suggestion import ProjectSuggestion
from makervault.schemas.project_suggestion import (
    ProjectSuggestionCreate,
    ProjectSuggestionListResponse,
    ProjectSuggestionResponse,
)
from makervault.ai.service import get_active_provider
from makervault.services.suggestion_service import run_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["suggestions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_suggestion_or_404(
    suggestion_id: uuid.UUID, db: AsyncSession
) -> ProjectSuggestion:
    obj = await db.get(ProjectSuggestion, suggestion_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ProjectSuggestion {suggestion_id} not found.",
        )
    return obj


# ---------------------------------------------------------------------------
# Create and run a suggestion
# ---------------------------------------------------------------------------


@router.post(
    "/suggestions",
    response_model=ProjectSuggestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and run a project suggestion",
)
async def create_suggestion(
    body: ProjectSuggestionCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectSuggestionResponse:
    """Create a project suggestion and run it immediately against current inventory.

    The suggestion status reflects the outcome:

    * ``done``   — AI returned one or more project ideas.
    * ``failed`` — no active provider or AI call errored.
    """
    suggestion = ProjectSuggestion(
        prompt=body.prompt,
        status="running",
    )
    db.add(suggestion)
    await db.flush()

    provider = await get_active_provider(db)
    if provider is None:
        suggestion.status = "failed"
        suggestion.error_message = (
            "No active AI provider configured. "
            "Add and enable a provider on the AI Settings page."
        )
        await db.flush()
        return ProjectSuggestionResponse.model_validate(suggestion)

    suggestion.provider_id = provider.config.id
    suggestion.provider_name = provider.config.name

    try:
        result = await run_suggestion(body.prompt, db, provider)
        suggestion.status = "done"
        suggestion.result_json = result
    except Exception as exc:
        logger.warning("Project suggestion %s failed: %s", suggestion.id, exc)
        suggestion.status = "failed"
        suggestion.error_message = str(exc)

    await db.flush()
    await db.refresh(suggestion)
    return ProjectSuggestionResponse.model_validate(suggestion)


# ---------------------------------------------------------------------------
# List suggestions
# ---------------------------------------------------------------------------


@router.get(
    "/suggestions",
    response_model=ProjectSuggestionListResponse,
    summary="List project suggestions",
)
async def list_suggestions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectSuggestionListResponse:
    total = (
        await db.execute(select(func.count()).select_from(ProjectSuggestion))
    ).scalar_one()
    result = await db.execute(
        select(ProjectSuggestion)
        .order_by(ProjectSuggestion.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return ProjectSuggestionListResponse(
        items=[ProjectSuggestionResponse.model_validate(s) for s in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# Get a single suggestion
# ---------------------------------------------------------------------------


@router.get(
    "/suggestions/{suggestion_id}",
    response_model=ProjectSuggestionResponse,
    summary="Get a project suggestion by ID",
)
async def get_suggestion(
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectSuggestionResponse:
    suggestion = await _get_suggestion_or_404(suggestion_id, db)
    return ProjectSuggestionResponse.model_validate(suggestion)


# ---------------------------------------------------------------------------
# Delete a suggestion
# ---------------------------------------------------------------------------


@router.delete(
    "/suggestions/{suggestion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project suggestion record",
)
async def delete_suggestion(
    suggestion_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    suggestion = await _get_suggestion_or_404(suggestion_id, db)
    await db.delete(suggestion)
