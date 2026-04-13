"""Category ORM model.

A Category provides a hierarchical taxonomy for Parts.
Categories are stored in a table (not hard-coded enums) so they can grow.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class Category(TimestampMixin, Base):
    """Hierarchical part category."""

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    parent: Mapped["Category | None"] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
        foreign_keys=[parent_category_id],
    )
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys=[parent_category_id],
    )
    parts: Mapped[list["Part"]] = relationship(  # noqa: F821
        "Part", back_populates="category"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} name={self.name!r}>"
