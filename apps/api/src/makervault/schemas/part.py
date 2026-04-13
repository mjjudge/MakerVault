"""Pydantic schemas for Part."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from makervault.models.part import PART_KIND_VALUES, PART_STATUS_VALUES
from makervault.schemas.base import BaseSchema


class PartCreate(BaseSchema):
    part_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    short_description: str | None = None
    long_description: str | None = None
    category_id: uuid.UUID | None = None
    part_kind: str | None = Field(default=None, pattern=f"^({'|'.join(PART_KIND_VALUES)})$")
    manufacturer: str | None = None
    manufacturer_part_number: str | None = None
    default_unit: str = "pcs"
    package_type: str | None = None
    spec_summary: str | None = None
    capabilities_json: dict[str, Any] | None = None
    tags: list[str] | None = None
    aliases: list[str] | None = None
    is_consumable: bool = False
    is_serialised: bool = False
    is_hazardous: bool = False
    is_active: bool = True
    status: str = Field(default="draft", pattern=f"^({'|'.join(PART_STATUS_VALUES)})$")
    needs_review: bool = False
    notes: str | None = None


class PartUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    short_description: str | None = None
    long_description: str | None = None
    category_id: uuid.UUID | None = None
    part_kind: str | None = Field(default=None, pattern=f"^({'|'.join(PART_KIND_VALUES)})$")
    manufacturer: str | None = None
    manufacturer_part_number: str | None = None
    default_unit: str | None = None
    package_type: str | None = None
    spec_summary: str | None = None
    capabilities_json: dict[str, Any] | None = None
    tags: list[str] | None = None
    aliases: list[str] | None = None
    is_consumable: bool | None = None
    is_serialised: bool | None = None
    is_hazardous: bool | None = None
    is_active: bool | None = None
    status: str | None = Field(default=None, pattern=f"^({'|'.join(PART_STATUS_VALUES)})$")
    needs_review: bool | None = None
    notes: str | None = None


class PartResponse(BaseSchema):
    id: uuid.UUID
    part_code: str
    name: str
    short_description: str | None
    long_description: str | None
    category_id: uuid.UUID | None
    part_kind: str | None
    manufacturer: str | None
    manufacturer_part_number: str | None
    default_unit: str
    package_type: str | None
    spec_summary: str | None
    capabilities_json: dict[str, Any] | None
    tags: list[str] | None
    aliases: list[str] | None
    is_consumable: bool
    is_serialised: bool
    is_hazardous: bool
    is_active: bool
    status: str
    identification_confidence: int | None
    needs_review: bool
    provenance: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("aliases", mode="before")
    @classmethod
    def _coerce_aliases(cls, v: Any) -> Any:
        """Accept a plain string (SQLite comma-sep storage) or native list."""
        if v is None or isinstance(v, list):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return None
            return [a.strip() for a in stripped.split(",") if a.strip()]
        return v


class PartListResponse(BaseSchema):
    items: list[PartResponse]
    total: int
