"""Pydantic schemas for Part."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from makervault.models.part import PART_KIND_VALUES, PART_STATUS_VALUES
from makervault.schemas.base import BaseSchema


def _coerce_str_list(v: Any) -> Any:
    """Accept None, a native list, or a comma-separated string (SQLite)."""
    if v is None or isinstance(v, list):
        return v
    if isinstance(v, str):
        stripped = v.strip()
        if not stripped:
            return None
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return v


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
    # Taxonomy
    category: str | None = None
    subcategory: str | None = None
    family: str | None = None
    # Electrical / interface
    form_factor: str | None = None
    interface: list[str] | None = None
    voltage: str | None = None
    logic_level: str | None = None
    # Functional
    pins: list[str] | None = None
    capabilities: list[str] | None = None
    use_cases: list[str] | None = None
    key_specs: dict[str, Any] | None = None
    # Flags
    protection_features: list[str] | None = None
    special_flags: list[str] | None = None


class PartUpdate(BaseSchema):
    part_code: str | None = Field(default=None, min_length=1, max_length=100)
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
    # Taxonomy
    category: str | None = None
    subcategory: str | None = None
    family: str | None = None
    # Electrical / interface
    form_factor: str | None = None
    interface: list[str] | None = None
    voltage: str | None = None
    logic_level: str | None = None
    # Functional
    pins: list[str] | None = None
    capabilities: list[str] | None = None
    use_cases: list[str] | None = None
    key_specs: dict[str, Any] | None = None
    # Flags
    protection_features: list[str] | None = None
    special_flags: list[str] | None = None


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
    # Taxonomy
    category: str | None = None
    subcategory: str | None = None
    family: str | None = None
    # Electrical / interface
    form_factor: str | None = None
    interface: list[str] | None = None
    voltage: str | None = None
    logic_level: str | None = None
    # Functional
    pins: list[str] | None = None
    capabilities: list[str] | None = None
    use_cases: list[str] | None = None
    key_specs: dict[str, Any] | None = None
    # Flags
    protection_features: list[str] | None = None
    special_flags: list[str] | None = None

    @field_validator("aliases", "tags", "interface", "pins",
                     "capabilities", "use_cases", "protection_features",
                     "special_flags", mode="before")
    @classmethod
    def _coerce_list(cls, v: Any) -> Any:
        return _coerce_str_list(v)


class PartListResponse(BaseSchema):
    items: list[PartResponse]
    total: int
