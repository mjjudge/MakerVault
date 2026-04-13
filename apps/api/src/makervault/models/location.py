"""Location ORM model.

A Location is a named physical place (room, shelf, zone).
Locations can be nested (e.g. Building → Room → Shelf).
Stock items can be placed directly in a Location or in a Container within one.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class Location(TimestampMixin, Base):
    """Physical location/place where stock or containers are stored."""

    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    parent: Mapped["Location | None"] = relationship(
        "Location",
        remote_side="Location.id",
        back_populates="children",
        foreign_keys=[parent_location_id],
    )
    children: Mapped[list["Location"]] = relationship(
        "Location",
        back_populates="parent",
        foreign_keys=[parent_location_id],
    )
    containers: Mapped[list["Container"]] = relationship(  # noqa: F821
        "Container",
        back_populates="location",
        foreign_keys="Container.location_id",
    )
    stock_items: Mapped[list["StockItem"]] = relationship(  # noqa: F821
        "StockItem",
        back_populates="location",
        foreign_keys="StockItem.location_id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location id={self.id} name={self.name!r}>"
