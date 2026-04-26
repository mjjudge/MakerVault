"""AI provider configuration router.

Endpoints
---------
GET    /api/ai/providers                      — list all provider configs
POST   /api/ai/providers                      — create a provider config
GET    /api/ai/providers/{id}                 — get a single provider config
PATCH  /api/ai/providers/{id}                 — update a provider config
DELETE /api/ai/providers/{id}                 — delete a provider config
POST   /api/ai/providers/{id}/health          — run a live health-check against the provider
GET    /api/ai/feature-assignments            — list per-feature provider assignments
PUT    /api/ai/feature-assignments/{feature}  — set (or clear) a feature's provider
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.ai.service import build_provider, get_provider_by_id
from makervault.database import get_db_session
from makervault.models.ai_feature_assignment import (
    AI_FEATURE_KEYS,
    AIFeatureAssignment,
)
from makervault.models.ai_provider_config import AIProviderConfig
from makervault.schemas.ai_feature_assignment import (
    AIFeatureAssignmentResponse,
    AIFeatureAssignmentUpdate,
)
from makervault.schemas.ai_provider_config import (
    AIProviderConfigCreate,
    AIProviderConfigResponse,
    AIProviderConfigUpdate,
    HealthCheckResponse,
)

router = APIRouter(prefix="/ai/providers", tags=["ai"])
feature_router = APIRouter(prefix="/ai/feature-assignments", tags=["ai"])


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AIProviderConfigResponse], summary="List AI provider configs")
async def list_providers(
    db: AsyncSession = Depends(get_db_session),
) -> list[AIProviderConfigResponse]:
    result = await db.execute(
        select(AIProviderConfig).order_by(
            AIProviderConfig.is_default.desc(),
            AIProviderConfig.name.asc(),
        )
    )
    configs = result.scalars().all()
    return [AIProviderConfigResponse.model_validate(c) for c in configs]


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AIProviderConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI provider config",
)
async def create_provider(
    body: AIProviderConfigCreate,
    db: AsyncSession = Depends(get_db_session),
) -> AIProviderConfigResponse:
    # Ensure name is unique.
    existing = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.name == body.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An AI provider named '{body.name}' already exists.",
        )

    # If this new provider is being set as default, clear existing defaults.
    if body.is_default:
        await _clear_defaults(db)

    config = AIProviderConfig(**body.model_dump())
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return AIProviderConfigResponse.model_validate(config)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


@router.get(
    "/{provider_id}",
    response_model=AIProviderConfigResponse,
    summary="Get an AI provider config",
)
async def get_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> AIProviderConfigResponse:
    config = await _get_or_404(db, provider_id)
    return AIProviderConfigResponse.model_validate(config)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.patch(
    "/{provider_id}",
    response_model=AIProviderConfigResponse,
    summary="Update an AI provider config",
)
async def update_provider(
    provider_id: uuid.UUID,
    body: AIProviderConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> AIProviderConfigResponse:
    config = await _get_or_404(db, provider_id)

    updates = body.model_dump(exclude_unset=True)

    # Check name uniqueness if name is being changed.
    if "name" in updates and updates["name"] != config.name:
        existing = await db.execute(
            select(AIProviderConfig).where(
                AIProviderConfig.name == updates["name"],
                AIProviderConfig.id != provider_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An AI provider named '{updates['name']}' already exists.",
            )

    # Validate base_url requirement if provider_type is being changed.
    new_type = updates.get("provider_type", config.provider_type)
    new_base_url = updates.get("base_url", config.base_url)
    if new_type in ("ollama", "openai_compatible") and not new_base_url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"base_url is required for provider_type='{new_type}'",
        )

    # If this provider is being set as default, clear existing defaults first.
    if updates.get("is_default"):
        await _clear_defaults(db, exclude_id=provider_id)

    for field, value in updates.items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)
    return AIProviderConfigResponse.model_validate(config)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an AI provider config",
)
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    config = await _get_or_404(db, provider_id)
    await db.delete(config)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@router.post(
    "/{provider_id}/health",
    response_model=HealthCheckResponse,
    summary="Run a live health-check against an AI provider",
)
async def health_check_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> HealthCheckResponse:
    config = await _get_or_404(db, provider_id)

    try:
        provider = build_provider(config)
    except EnvironmentError as exc:
        return HealthCheckResponse(
            provider_id=config.id,
            provider_name=config.name,
            healthy=False,
            detail=str(exc),
        )

    healthy = await provider.health_check()
    return HealthCheckResponse(
        provider_id=config.id,
        provider_name=config.name,
        healthy=healthy,
        detail=None if healthy else "Provider did not respond successfully.",
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_or_404(db: AsyncSession, provider_id: uuid.UUID) -> AIProviderConfig:
    config = await db.get(AIProviderConfig, provider_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI provider config {provider_id} not found.",
        )
    return config


async def _clear_defaults(
    db: AsyncSession, exclude_id: uuid.UUID | None = None
) -> None:
    """Set is_default=False for all providers (except optionally one)."""
    result = await db.execute(
        select(AIProviderConfig).where(AIProviderConfig.is_default.is_(True))
    )
    for row in result.scalars().all():
        if exclude_id is None or row.id != exclude_id:
            row.is_default = False
    await db.flush()


# ---------------------------------------------------------------------------
# Feature assignments
# ---------------------------------------------------------------------------


async def _build_feature_response(
    feature_key: str,
    assignment: AIFeatureAssignment | None,
    db: AsyncSession,
) -> AIFeatureAssignmentResponse:
    provider_name: str | None = None
    provider_id: uuid.UUID | None = None
    updated_at = datetime.now(timezone.utc)

    if assignment is not None:
        provider_id = assignment.provider_id
        updated_at = assignment.updated_at
        if provider_id is not None:
            cfg = await db.get(AIProviderConfig, provider_id)
            provider_name = cfg.name if cfg else None

    return AIFeatureAssignmentResponse.from_feature_key(
        feature_key=feature_key,
        provider_id=provider_id,
        provider_name=provider_name,
        updated_at=updated_at,
    )


@feature_router.get(
    "",
    response_model=list[AIFeatureAssignmentResponse],
    summary="List per-feature AI provider assignments",
)
async def list_feature_assignments(
    db: AsyncSession = Depends(get_db_session),
) -> list[AIFeatureAssignmentResponse]:
    """Return one entry per known AI feature, with its assigned provider (or null)."""
    result = await db.execute(select(AIFeatureAssignment))
    rows: dict[str, AIFeatureAssignment] = {r.feature_key: r for r in result.scalars().all()}

    responses = []
    for key in AI_FEATURE_KEYS:
        responses.append(await _build_feature_response(key, rows.get(key), db))
    return responses


@feature_router.put(
    "/{feature_key}",
    response_model=AIFeatureAssignmentResponse,
    summary="Set (or clear) the AI provider for a feature",
)
async def set_feature_assignment(
    feature_key: str,
    body: AIFeatureAssignmentUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> AIFeatureAssignmentResponse:
    """Assign a specific provider to *feature_key*, or pass ``provider_id: null``
    to clear the assignment and fall back to the global default."""
    if feature_key not in AI_FEATURE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown feature key '{feature_key}'. Valid keys: {list(AI_FEATURE_KEYS)}",
        )

    if body.provider_id is not None:
        cfg = await db.get(AIProviderConfig, body.provider_id)
        if cfg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI provider {body.provider_id} not found.",
            )

    assignment = await db.get(AIFeatureAssignment, feature_key)
    if assignment is None:
        assignment = AIFeatureAssignment(feature_key=feature_key)
        db.add(assignment)

    assignment.provider_id = body.provider_id
    assignment.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return await _build_feature_response(feature_key, assignment, db)
