"""AIFeatureAssignment ORM model.

Maps each AI-powered feature (enrichment job type) to a specific
AI provider. When a feature has no assignment, the default enabled
provider is used as a fallback.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from makervault.database import Base

# All known AI feature keys — one per enrichment job type.
AI_FEATURE_KEYS = (
    "summarise_document",
    "extract_metadata",
    "generate_aliases",
    "classify_part",
    "enrich_part",
)

AI_FEATURE_LABELS: dict[str, str] = {
    "summarise_document": "Summarise Document",
    "extract_metadata": "Extract Document Metadata",
    "generate_aliases": "Generate Part Aliases",
    "classify_part": "Classify Part",
    "enrich_part": "Enrich Part (full schema)",
}


class AIFeatureAssignment(Base):
    """Maps an AI feature to its designated provider.

    One row per feature key.  ``provider_id = NULL`` means "use the default
    provider" — i.e. the row can exist just to record the intent even before
    a provider is chosen.
    """

    __tablename__ = "ai_feature_assignments"

    feature_key: Mapped[str] = mapped_column(Text, primary_key=True)

    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AIFeatureAssignment feature={self.feature_key!r} "
            f"provider_id={self.provider_id}>"
        )
