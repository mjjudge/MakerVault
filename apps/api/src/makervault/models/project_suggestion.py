"""ProjectSuggestion ORM model.

A ProjectSuggestion represents a single AI-assisted "what can I build?" query.
The user supplies a free-text prompt; the service builds a grounded inventory
context, calls the active AI provider, and stores the structured result.

Job lifecycle
-------------
pending  → running  → done      (suggestions ready for review)
                     → failed    (AI call errored or parse failed)
"""

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

# ---------------------------------------------------------------------------
# Enumeration values
# ---------------------------------------------------------------------------

SUGGESTION_STATUS_VALUES = (
    "pending",
    "running",
    "done",
    "failed",
)


class ProjectSuggestion(TimestampMixin, Base):
    """A single AI project-inspiration query grounded in current inventory.

    ``result_json`` stores the parsed AI response:

    .. code-block:: json

        {
          "suggestions": [
            {
              "title": "LED Matrix Clock",
              "description": "Build a clock using your ESP32...",
              "difficulty": "intermediate",
              "owned_parts": [
                {"part_id": "uuid", "part_name": "ESP32 DevKit V1"}
              ],
              "missing_parts": [
                {"name": "MAX7219 LED Matrix", "notes": "inexpensive, ~$3"}
              ]
            }
          ]
        }
    """

    __tablename__ = "project_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    # User's free-text prompt.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    # Which provider ran this suggestion.
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # Denormalised provider name kept for display even if provider is later deleted.
    provider_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsed AI output — list of project suggestions with grounded part references.
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Human-readable error message when status == "failed".
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ProjectSuggestion id={self.id} status={self.status!r} "
            f"prompt={self.prompt[:40]!r}>"
        )
