"""Pydantic schemas for EnrichmentJob."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from makervault.models.enrichment_job import (
    ENRICHMENT_ENTITY_TYPE_VALUES,
    ENRICHMENT_JOB_STATUS_VALUES,
    ENRICHMENT_JOB_TYPE_VALUES,
)
from makervault.schemas.base import BaseSchema


class EnrichmentJobCreate(BaseSchema):
    job_type: str = Field(
        ...,
        pattern=f"^({'|'.join(ENRICHMENT_JOB_TYPE_VALUES)})$",
    )
    entity_type: str = Field(
        ...,
        pattern=f"^({'|'.join(ENRICHMENT_ENTITY_TYPE_VALUES)})$",
    )
    entity_id: uuid.UUID


class EnrichmentJobResponse(BaseSchema):
    id: uuid.UUID
    job_type: str
    entity_type: str
    entity_id: uuid.UUID
    status: str
    provider_id: uuid.UUID | None
    provider_name: str | None
    result_json: dict[str, Any] | None
    confidence: int | None
    error_message: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnrichmentJobListResponse(BaseSchema):
    items: list[EnrichmentJobResponse]
    total: int
