"""AIProviderConfig ORM model.

Stores the *configuration* of an AI provider (type, endpoint, model, etc.).
API keys are **never** stored here — they come from environment variables.
The ``api_key_env_var`` field records which environment variable holds the key,
so operators know what to set without the application ever persisting the secret.
"""

import uuid

from sqlalchemy import Boolean, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

PROVIDER_TYPE_VALUES = (
    "openai",
    "anthropic",
    "ollama",
    "openai_compatible",
)


class AIProviderConfig(TimestampMixin, Base):
    """Persisted configuration for an AI provider.

    Secrets (API keys) are **not** stored here.  ``api_key_env_var`` records the
    *name* of the environment variable that holds the key — the application
    resolves it at runtime via ``os.environ``.
    """

    __tablename__ = "ai_provider_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    # Human-readable label, e.g. "Local Ollama" or "OpenAI GPT-4o"
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    provider_type: Mapped[str] = mapped_column(
        Enum(*PROVIDER_TYPE_VALUES, name="ai_provider_type_enum", create_type=True),
        nullable=False,
    )

    # Base URL for the API endpoint.
    # Required for ollama / openai_compatible; optional override for openai / anthropic.
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Default model identifier, e.g. "gpt-4o", "llama3", "claude-3-5-haiku-latest"
    model: Mapped[str] = mapped_column(Text, nullable=False)

    # Name of the environment variable that holds the API key (NOT the key itself).
    # e.g. "OPENAI_API_KEY", "ANTHROPIC_API_KEY".
    # NULL for local providers that require no key (e.g. Ollama with no auth).
    api_key_env_var: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Whether this provider is available for use.
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Whether this is the default provider selected for new AI tasks.
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Free-form notes (e.g. "Used for document summarisation only")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AIProviderConfig id={self.id} name={self.name!r} "
            f"type={self.provider_type!r} enabled={self.is_enabled}>"
        )
