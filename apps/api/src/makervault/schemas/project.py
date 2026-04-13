"""Pydantic schemas for Project and ProjectPart (BOM entry)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from makervault.models.project import PROJECT_STATUS_VALUES
from makervault.schemas.base import BaseSchema
from makervault.schemas.part import PartResponse


# ---------------------------------------------------------------------------
# Project schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    status: str = Field(
        default="active",
        pattern=f"^({'|'.join(PROJECT_STATUS_VALUES)})$",
    )
    notes: str | None = None


class ProjectUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: str | None = Field(
        default=None,
        pattern=f"^({'|'.join(PROJECT_STATUS_VALUES)})$",
    )
    notes: str | None = None


class ProjectResponse(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseSchema):
    items: list[ProjectResponse]
    total: int


# ---------------------------------------------------------------------------
# ProjectPart (BOM entry) schemas
# ---------------------------------------------------------------------------


class ProjectPartCreate(BaseSchema):
    part_id: uuid.UUID
    quantity_required: Decimal = Field(default=Decimal("1"), gt=0)
    unit: str | None = None
    notes: str | None = None


class ProjectPartUpdate(BaseSchema):
    quantity_required: Decimal | None = Field(default=None, gt=0)
    unit: str | None = None
    notes: str | None = None


class ProjectPartResponse(BaseSchema):
    id: uuid.UUID
    project_id: uuid.UUID
    part_id: uuid.UUID
    quantity_required: Decimal
    unit: str | None
    notes: str | None
    part: PartResponse
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# BOM availability
# ---------------------------------------------------------------------------


class BOMEntryAvailability(BaseSchema):
    project_part_id: uuid.UUID
    part_id: uuid.UUID
    part_code: str
    part_name: str
    quantity_required: Decimal
    total_in_stock: Decimal
    is_available: bool


class BOMAvailabilityResponse(BaseSchema):
    project_id: uuid.UUID
    entries: list[BOMEntryAvailability]
    all_available: bool
