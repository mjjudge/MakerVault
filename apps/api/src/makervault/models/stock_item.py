"""StockItem ORM model.

A StockItem represents a specific physical instance (or batch) that you own,
placed at a specific location.

Placement rule:
- A StockItem must have exactly ONE of: container_id OR location_id.
  Both null or both set is invalid.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

STOCK_STATUS_VALUES = (
    "available",
    "reserved",
    "consumed",
    "missing",
    "damaged",
    "unknown",
)

STOCK_CONDITION_VALUES = (
    "new",
    "used",
    "untested",
    "faulty",
    "for_parts",
)


class StockItem(TimestampMixin, Base):
    """A physical instance or batch of a Part that is owned and stored."""

    __tablename__ = "stock_items"

    __table_args__ = (
        # Exactly one of location_id or container_id must be set.
        CheckConstraint(
            "CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN container_id IS NOT NULL THEN 1 ELSE 0 END = 1",
            name="ck_stock_item_single_placement",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Placement — exactly one of these must be set
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    container_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=1)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum(*STOCK_STATUS_VALUES, name="stock_status_enum", create_type=True),
        nullable=False,
        default="available",
    )
    condition: Mapped[str | None] = mapped_column(
        Enum(*STOCK_CONDITION_VALUES, name="stock_condition_enum", create_type=True),
        nullable=True,
    )

    serial_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    purchase_currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_reserved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="stock_items")  # noqa: F821
    location: Mapped["Location | None"] = relationship(  # noqa: F821
        "Location",
        back_populates="stock_items",
        foreign_keys=[location_id],
    )
    container: Mapped["Container | None"] = relationship(  # noqa: F821
        "Container",
        back_populates="stock_items",
        foreign_keys=[container_id],
    )
    document_links: Mapped[list["StockItemDocument"]] = relationship(  # noqa: F821
        "StockItemDocument", back_populates="stock_item", cascade="all, delete-orphan"
    )
    usage_history: Mapped[list["UsageHistory"]] = relationship(  # noqa: F821
        "UsageHistory", back_populates="stock_item", passive_deletes=True
    )

    @validates("location_id", "container_id")
    def validate_single_placement(self, key: str, value):
        """Python-side guard against dual or null placement."""
        if key == "location_id" and value is not None and self.container_id is not None:
            raise ValueError(
                "A StockItem cannot have both a location_id and a container_id."
            )
        if key == "container_id" and value is not None and self.location_id is not None:
            raise ValueError(
                "A StockItem cannot have both a location_id and a container_id."
            )
        return value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockItem id={self.id} part_id={self.part_id}>"
