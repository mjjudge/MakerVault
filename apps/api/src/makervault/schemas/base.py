"""Shared Pydantic schema utilities."""

import uuid

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with shared configuration."""

    model_config = ConfigDict(from_attributes=True)


class UUIDSchema(BaseSchema):
    id: uuid.UUID
