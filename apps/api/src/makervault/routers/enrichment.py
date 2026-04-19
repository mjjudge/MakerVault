"""Enrichment jobs API router.

Endpoints
---------
POST   /enrichment/jobs                  — create and immediately run a job
GET    /enrichment/jobs                  — list jobs (filterable)
GET    /enrichment/jobs/{id}             — get a single job
POST   /enrichment/jobs/{id}/apply       — apply the result to the target entity
POST   /enrichment/jobs/{id}/dismiss     — mark the result as dismissed
DELETE /enrichment/jobs/{id}             — delete a job record
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.document import Document
from makervault.models.enrichment_job import (
    ENRICHMENT_ENTITY_TYPE_VALUES,
    ENRICHMENT_JOB_STATUS_VALUES,
    ENRICHMENT_JOB_TYPE_VALUES,
    EnrichmentJob,
)
from makervault.models.part import Part
from makervault.models.part_alias import PartAlias
from makervault.routers.part_aliases import _sync_aliases_array
from makervault.schemas.enrichment_job import (
    EnrichmentJobCreate,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
)
from makervault.ai.service import get_active_provider
from makervault.services.enrichment_service import run_enrichment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["enrichment"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_job_or_404(job_id: uuid.UUID, db: AsyncSession) -> EnrichmentJob:
    job = await db.get(EnrichmentJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EnrichmentJob {job_id} not found.",
        )
    return job


async def _resolve_entity(entity_type: str, entity_id: uuid.UUID, db: AsyncSession):
    """Return the Part or Document for *entity_type* / *entity_id*, or raise 404."""
    if entity_type == "part":
        obj = await db.get(Part, entity_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"Part {entity_id} not found.")
    elif entity_type == "document":
        obj = await db.get(Document, entity_id)
        if obj is None:
            raise HTTPException(status_code=404, detail=f"Document {entity_id} not found.")
    else:
        raise HTTPException(status_code=422, detail=f"Unknown entity_type: {entity_type!r}")
    return obj


# ---------------------------------------------------------------------------
# Job type / entity type compatibility
# ---------------------------------------------------------------------------

_DOCUMENT_JOBS = {"summarise_document", "extract_metadata"}
_PART_JOBS = {"generate_aliases", "classify_part", "enrich_part"}


def _validate_job_entity_compat(job_type: str, entity_type: str) -> None:
    if job_type in _DOCUMENT_JOBS and entity_type != "document":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"job_type '{job_type}' requires entity_type 'document'.",
        )
    if job_type in _PART_JOBS and entity_type != "part":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"job_type '{job_type}' requires entity_type 'part'.",
        )


# ---------------------------------------------------------------------------
# Create and run a job
# ---------------------------------------------------------------------------


@router.post(
    "/enrichment/jobs",
    response_model=EnrichmentJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and run an enrichment job",
)
async def create_enrichment_job(
    body: EnrichmentJobCreate,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    """Create an enrichment job and run it immediately.

    The job status reflects the outcome:
    * ``done``   — AI returned a result that can be applied.
    * ``failed`` — no active provider or AI call errored.
    """
    _validate_job_entity_compat(body.job_type, body.entity_type)
    entity = await _resolve_entity(body.entity_type, body.entity_id, db)

    job = EnrichmentJob(
        job_type=body.job_type,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        status="running",
    )
    db.add(job)
    await db.flush()

    provider = await get_active_provider(db)
    if provider is None:
        job.status = "failed"
        job.error_message = (
            "No active AI provider configured. "
            "Add and enable a provider on the AI Settings page."
        )
        await db.flush()
        return EnrichmentJobResponse.model_validate(job)

    job.provider_id = provider.config.id
    job.provider_name = provider.config.name

    try:
        result_json, confidence = await run_enrichment(body.job_type, entity, provider)
        job.status = "done"
        job.result_json = result_json
        job.confidence = confidence
    except Exception as exc:
        logger.warning("Enrichment job %s failed: %s", job.id, exc)
        job.status = "failed"
        job.error_message = str(exc)

    await db.flush()
    await db.refresh(job)
    return EnrichmentJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# List jobs
# ---------------------------------------------------------------------------


@router.get(
    "/enrichment/jobs",
    response_model=EnrichmentJobListResponse,
    summary="List enrichment jobs",
)
async def list_enrichment_jobs(
    entity_type: str | None = Query(default=None),
    entity_id: uuid.UUID | None = Query(default=None),
    job_type: str | None = Query(default=None),
    job_status: str | None = Query(default=None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobListResponse:
    query = select(EnrichmentJob)
    count_query = select(func.count()).select_from(EnrichmentJob)

    filters = []
    if entity_type is not None:
        filters.append(EnrichmentJob.entity_type == entity_type)
    if entity_id is not None:
        filters.append(EnrichmentJob.entity_id == entity_id)
    if job_type is not None:
        filters.append(EnrichmentJob.job_type == job_type)
    if job_status is not None:
        filters.append(EnrichmentJob.status == job_status)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(EnrichmentJob.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return EnrichmentJobListResponse(
        items=[EnrichmentJobResponse.model_validate(j) for j in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# Get a single job
# ---------------------------------------------------------------------------


@router.get(
    "/enrichment/jobs/{job_id}",
    response_model=EnrichmentJobResponse,
    summary="Get an enrichment job by ID",
)
async def get_enrichment_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    job = await _get_job_or_404(job_id, db)
    return EnrichmentJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# Apply a job result
# ---------------------------------------------------------------------------


@router.post(
    "/enrichment/jobs/{job_id}/apply",
    response_model=EnrichmentJobResponse,
    summary="Apply an enrichment job result to the target entity",
)
async def apply_enrichment_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    """Apply the result stored in a ``done`` job to the target entity.

    * ``summarise_document``  → sets ``document.summary``
    * ``extract_metadata``    → sets ``document.metadata_json`` and individual
                                fields (manufacturer, part_number, package_type)
    * ``generate_aliases``    → creates ``PartAlias`` rows for each suggested alias
    * ``classify_part``       → updates ``part.part_kind`` and ``part.tags``
    """
    job = await _get_job_or_404(job_id, db)

    if job.status not in ("done",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is in status '{job.status}'; only 'done' jobs can be applied.",
        )
    if job.result_json is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job has no result to apply.",
        )

    entity = await _resolve_entity(job.entity_type, job.entity_id, db)
    result = job.result_json

    if job.job_type == "summarise_document":
        entity.summary = result.get("summary") or entity.summary  # type: ignore[attr-defined]

    elif job.job_type == "extract_metadata":
        entity.metadata_json = result  # type: ignore[attr-defined]
        if result.get("manufacturer"):
            entity.manufacturer = result["manufacturer"]  # type: ignore[attr-defined]
        if result.get("part_number"):
            entity.manufacturer_part_number = result["part_number"]  # type: ignore[attr-defined]
        if result.get("package_type"):
            entity.package_type = result["package_type"]  # type: ignore[attr-defined]

    elif job.job_type == "generate_aliases":
        aliases: list[str] = result.get("aliases") or []
        existing_result = await db.execute(
            select(PartAlias).where(PartAlias.part_id == job.entity_id)
        )
        existing_aliases = {a.alias for a in existing_result.scalars().all()}
        for alias_text in aliases:
            if alias_text and alias_text not in existing_aliases:
                db.add(PartAlias(part_id=job.entity_id, alias=alias_text))
        await db.flush()
        # Rebuild denormalised aliases array (handles SQLite vs PostgreSQL)
        part = entity  # type: ignore[assignment]
        await _sync_aliases_array(part, db)

    elif job.job_type == "classify_part":
        part = entity  # type: ignore[assignment]

        try:
            is_pg = db.sync_session.get_bind().dialect.name == "postgresql"
        except Exception:
            is_pg = True

        if result.get("part_kind"):
            from makervault.models.part import PART_KIND_VALUES
            if result["part_kind"] in PART_KIND_VALUES:
                part.part_kind = result["part_kind"]

        if is_pg and result.get("tags"):
            existing_tags = list(part.tags or [])
            for tag in result["tags"]:
                if tag and tag not in existing_tags:
                    existing_tags.append(tag)
            part.tags = existing_tags or None

    elif job.job_type == "enrich_part":
        part = entity  # type: ignore[assignment]

        try:
            is_pg = db.sync_session.get_bind().dialect.name == "postgresql"
        except Exception:
            is_pg = True

        # Plain text fields — always safe to set
        for field in ("category", "subcategory", "family", "form_factor",
                      "voltage", "logic_level"):
            val = result.get(field)
            if val:
                setattr(part, field, val)

        if is_pg:
            # ARRAY and JSONB fields — PostgreSQL only
            for field in ("interface", "pins", "capabilities", "use_cases",
                          "protection_features", "special_flags"):
                val = result.get(field)
                if isinstance(val, list) and val:
                    setattr(part, field, val)

            if isinstance(result.get("key_specs"), dict) and result["key_specs"]:
                part.key_specs = result["key_specs"]

    job.applied_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(job)
    return EnrichmentJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# Dismiss a job result
# ---------------------------------------------------------------------------


@router.post(
    "/enrichment/jobs/{job_id}/dismiss",
    response_model=EnrichmentJobResponse,
    summary="Dismiss an enrichment job result",
)
async def dismiss_enrichment_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> EnrichmentJobResponse:
    job = await _get_job_or_404(job_id, db)
    if job.status not in ("done",):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is in status '{job.status}'; only 'done' jobs can be dismissed.",
        )
    job.status = "dismissed"
    await db.flush()
    await db.refresh(job)
    return EnrichmentJobResponse.model_validate(job)


# ---------------------------------------------------------------------------
# Delete a job
# ---------------------------------------------------------------------------


@router.delete(
    "/enrichment/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an enrichment job record",
)
async def delete_enrichment_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    job = await _get_job_or_404(job_id, db)
    await db.delete(job)
