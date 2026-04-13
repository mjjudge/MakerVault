"""Pydantic schemas for Location."""

import uuid
from datetime import datetime

from pydantic import Field

from makervault.schemas.base import BaseSchema


class LocationCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    parent_location_id: uuid.UUID | None = None


class LocationUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    parent_location_id: uuid.UUID | None = None


class LocationResponse(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    parent_location_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class LocationListResponse(BaseSchema):
    items: list[LocationResponse]
    total: int
