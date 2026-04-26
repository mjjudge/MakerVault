"""Pydantic schemas for AIFeatureAssignment."""

import uuid
from datetime import datetime

from pydantic import Field

from makervault.models.ai_feature_assignment import AI_FEATURE_KEYS, AI_FEATURE_LABELS
from makervault.schemas.base import BaseSchema

_FEATURE_PATTERN = f"^({'|'.join(AI_FEATURE_KEYS)})$"


class AIFeatureAssignmentUpdate(BaseSchema):
    """Payload for setting (or clearing) a feature's provider assignment."""

    provider_id: uuid.UUID | None = Field(
        default=None,
        description="Provider to use for this feature. Null clears the assignment (use default).",
    )


class AIFeatureAssignmentResponse(BaseSchema):
    """Full representation of a feature assignment, including labels."""

    feature_key: str
    feature_label: str
    provider_id: uuid.UUID | None
    provider_name: str | None
    updated_at: datetime

    @classmethod
    def from_feature_key(
        cls,
        feature_key: str,
        provider_id: uuid.UUID | None,
        provider_name: str | None,
        updated_at: datetime,
    ) -> "AIFeatureAssignmentResponse":
        return cls(
            feature_key=feature_key,
            feature_label=AI_FEATURE_LABELS.get(feature_key, feature_key),
            provider_id=provider_id,
            provider_name=provider_name,
            updated_at=updated_at,
        )
