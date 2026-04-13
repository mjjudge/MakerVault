"""Pydantic schemas for UsageHistory."""

import uuid
from datetime import datetime

from pydantic import Field

from makervault.models.usage_history import USAGE_ACTION_TYPES
from makervault.schemas.base import BaseSchema


class UsageHistoryCreate(BaseSchema):
    stock_item_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    part_id: uuid.UUID | None = None
    action_type: str = Field(
        pattern=f"^({'|'.join(USAGE_ACTION_TYPES)})$",
    )
    quantity_delta: float | None = None
    used_at: datetime | None = None
    notes: str | None = None


class UsageHistoryResponse(BaseSchema):
    id: uuid.UUID
    stock_item_id: uuid.UUID | None
    project_id: uuid.UUID | None
    part_id: uuid.UUID | None
    action_type: str
    quantity_delta: float | None
    used_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime


class UsageHistoryListResponse(BaseSchema):
    items: list[UsageHistoryResponse]
    total: int
