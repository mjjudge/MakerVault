"""Pydantic schemas for Category."""

import uuid
from datetime import datetime

from pydantic import Field

from makervault.schemas.base import BaseSchema


class CategoryCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    parent_category_id: uuid.UUID | None = None
    description: str | None = None
    sort_order: int | None = None


class CategoryUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    parent_category_id: uuid.UUID | None = None
    description: str | None = None
    sort_order: int | None = None


class CategoryResponse(BaseSchema):
    id: uuid.UUID
    name: str
    parent_category_id: uuid.UUID | None
    description: str | None
    sort_order: int | None
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseSchema):
    items: list[CategoryResponse]
    total: int
