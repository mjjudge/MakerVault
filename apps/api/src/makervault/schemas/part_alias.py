"""Pydantic schemas for PartAlias."""
import uuid
from datetime import datetime
from pydantic import Field
from makervault.schemas.base import BaseSchema


class PartAliasCreate(BaseSchema):
    alias: str = Field(..., min_length=1, max_length=200)
    notes: str | None = None


class PartAliasResponse(BaseSchema):
    id: uuid.UUID
    part_id: uuid.UUID
    alias: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
