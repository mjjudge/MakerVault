"""Pydantic schemas for Container."""

import uuid
from datetime import datetime

from pydantic import Field, model_validator

from makervault.schemas.base import BaseSchema


class ContainerCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    label_code: str | None = None
    location_id: uuid.UUID | None = None
    parent_container_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_single_parent(self) -> "ContainerCreate":
        if self.location_id is not None and self.parent_container_id is not None:
            raise ValueError(
                "A container must have exactly one parent: "
                "either location_id or parent_container_id, not both."
            )
        if self.location_id is None and self.parent_container_id is None:
            raise ValueError(
                "A container must have exactly one parent: "
                "provide either location_id or parent_container_id."
            )
        return self


class ContainerUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    label_code: str | None = None
    location_id: uuid.UUID | None = None
    parent_container_id: uuid.UUID | None = None


class ContainerResponse(BaseSchema):
    id: uuid.UUID
    name: str
    description: str | None
    label_code: str | None
    location_id: uuid.UUID | None
    parent_container_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ContainerListResponse(BaseSchema):
    items: list[ContainerResponse]
    total: int
