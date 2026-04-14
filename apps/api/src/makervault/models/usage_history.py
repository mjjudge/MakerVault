"""UsageHistory ORM model.

Tracks what was actually used, consumed, moved, tested, or damaged.
Each row represents a lifecycle event for a StockItem, optionally
linked to a Project and denormalised with the Part reference for
efficient querying.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

USAGE_ACTION_TYPES = (
    "allocated",
    "used",
    "returned",
    "consumed",
    "tested",
    "damaged",
)


class UsageHistory(TimestampMixin, Base):
    """A single lifecycle event for a StockItem."""

    __tablename__ = "usage_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    # Optional FK to the stock item this event concerns
    stock_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Optional FK to a project this usage is linked to
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Denormalised part reference for efficient querying without joining
    # through stock_items
    part_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action_type: Mapped[str] = mapped_column(
        Enum(*USAGE_ACTION_TYPES, name="usage_action_type_enum", create_type=True),
        nullable=False,
    )

    # Positive = increase (e.g. returned), negative = decrease (e.g. consumed)
    quantity_delta: Mapped[float | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    stock_item: Mapped["StockItem | None"] = relationship(  # noqa: F821
        "StockItem", back_populates="usage_history"
    )
    project: Mapped["Project | None"] = relationship(  # noqa: F821
        "Project", back_populates="usage_history"
    )
    part: Mapped["Part | None"] = relationship("Part")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UsageHistory id={self.id} action={self.action_type} "
            f"stock_item_id={self.stock_item_id}>"
        )
