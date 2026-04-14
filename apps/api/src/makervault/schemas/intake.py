"""Pydantic schemas for the part intake workflow (Epic 14)."""

import uuid
from typing import Any

from pydantic import Field

from makervault.schemas.base import BaseSchema


class IntakeMatchRequest(BaseSchema):
    """Free-text intake request — describe a part in plain English."""

    description: str = Field(..., min_length=1, max_length=500)
    category_id: uuid.UUID | None = None


class IntakeCandidate(BaseSchema):
    """A ranked existing-part match candidate."""

    part_id: uuid.UUID
    part_code: str
    name: str
    short_description: str | None
    manufacturer: str | None
    manufacturer_part_number: str | None
    part_kind: str | None
    confidence: int = Field(..., ge=0, le=100, description="Match confidence 0–100")
    match_reason: str


class StorageSuggestion(BaseSchema):
    """A suggested placement (location or container) for the new stock item."""

    location_id: uuid.UUID | None = None
    container_id: uuid.UUID | None = None
    name: str
    score: int = Field(..., ge=0, le=100, description="Placement confidence 0–100")
    reason: str


class IntakeMatchResponse(BaseSchema):
    """Full response for a part-intake match request."""

    description: str
    normalised_tokens: list[str]
    candidates: list[IntakeCandidate]
    suggested_part_code: str
    storage_suggestions: list[StorageSuggestion]


class SuggestCodeRequest(BaseSchema):
    """Standalone code-suggestion request."""

    description: str = Field(..., min_length=1, max_length=500)


class SuggestCodeResponse(BaseSchema):
    """Suggested unique part code."""

    suggested_part_code: str
