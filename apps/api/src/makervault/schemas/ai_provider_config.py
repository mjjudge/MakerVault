"""Pydantic schemas for AIProviderConfig."""

import uuid
from datetime import datetime

from pydantic import Field, model_validator

from makervault.models.ai_provider_config import PROVIDER_TYPE_VALUES
from makervault.schemas.base import BaseSchema

_PROVIDER_PATTERN = f"^({'|'.join(PROVIDER_TYPE_VALUES)})$"


class AIProviderConfigCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=200)
    provider_type: str = Field(..., pattern=_PROVIDER_PATTERN)
    base_url: str | None = None
    model: str = Field(..., min_length=1, max_length=200)
    # Name of the env var holding the API key — NOT the key itself.
    api_key_env_var: str | None = None
    is_enabled: bool = True
    is_default: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def _base_url_required_for_local(self) -> "AIProviderConfigCreate":
        if self.provider_type in ("ollama", "openai_compatible") and not self.base_url:
            raise ValueError(
                f"base_url is required for provider_type='{self.provider_type}'"
            )
        return self


class AIProviderConfigUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    provider_type: str | None = Field(default=None, pattern=_PROVIDER_PATTERN)
    base_url: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    api_key_env_var: str | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    notes: str | None = None


class AIProviderConfigResponse(BaseSchema):
    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str | None
    model: str
    # The env var NAME is safe to return — the key value is never stored.
    api_key_env_var: str | None
    is_enabled: bool
    is_default: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


class HealthCheckResponse(BaseSchema):
    provider_id: uuid.UUID
    provider_name: str
    healthy: bool
    detail: str | None = None
