"""Container ORM model.

A Container is a physical storage object (box, tray, case, drawer) located
within a Location or nested inside another Container.

Placement rule:
- A Container must have exactly ONE of: location_id OR parent_container_id.
  Both null or both set is invalid.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class Container(TimestampMixin, Base):
    """A physical storage object that holds stock items or other containers."""

    __tablename__ = "containers"

    __table_args__ = (
        # Exactly one of location_id or parent_container_id must be set.
        CheckConstraint(
            "CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN parent_container_id IS NOT NULL THEN 1 ELSE 0 END = 1",
            name="ck_container_single_parent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    label_code: Mapped[str | None] = mapped_column(
        Text, nullable=True, unique=True, index=True
    )

    # Placement: either inside a Location or inside another Container
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    parent_container_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("containers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Relationships
    location: Mapped["Location | None"] = relationship(  # noqa: F821
        "Location",
        back_populates="containers",
        foreign_keys=[location_id],
    )
    parent_container: Mapped["Container | None"] = relationship(
        "Container",
        remote_side="Container.id",
        back_populates="child_containers",
        foreign_keys=[parent_container_id],
    )
    child_containers: Mapped[list["Container"]] = relationship(
        "Container",
        back_populates="parent_container",
        foreign_keys=[parent_container_id],
    )
    stock_items: Mapped[list["StockItem"]] = relationship(  # noqa: F821
        "StockItem",
        back_populates="container",
        foreign_keys="StockItem.container_id",
    )

    @validates("location_id", "parent_container_id")
    def validate_single_parent(self, key: str, value):
        """Enforce that exactly one parent is set (Python-side guard)."""
        if key == "location_id" and value is not None and self.parent_container_id is not None:
            raise ValueError(
                "A Container cannot have both a location_id and a parent_container_id."
            )
        if key == "parent_container_id" and value is not None and self.location_id is not None:
            raise ValueError(
                "A Container cannot have both a location_id and a parent_container_id."
            )
        return value

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Container id={self.id} name={self.name!r}>"
