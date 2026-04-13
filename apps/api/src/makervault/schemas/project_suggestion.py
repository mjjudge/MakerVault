"""Pydantic schemas for ProjectSuggestion."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from makervault.schemas.base import BaseSchema


class ProjectSuggestionCreate(BaseSchema):
    """Request body for creating a project suggestion."""

    prompt: str = Field(..., min_length=1, max_length=2000)


class ProjectSuggestionResponse(BaseSchema):
    """Full project suggestion record returned by the API."""

    id: uuid.UUID
    prompt: str
    status: str
    provider_id: uuid.UUID | None
    provider_name: str | None
    result_json: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ProjectSuggestionListResponse(BaseSchema):
    items: list[ProjectSuggestionResponse]
    total: int
