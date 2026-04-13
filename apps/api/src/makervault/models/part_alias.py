"""PartAlias ORM model.

Each row is one alias name for a Part. The denormalised Part.aliases
array is kept in sync with these rows whenever aliases are added or removed.
"""
import uuid
from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class PartAlias(TimestampMixin, Base):
    """A single alternate name or common alias for a Part."""

    __tablename__ = "part_aliases"

    __table_args__ = (
        UniqueConstraint("part_id", "alias", name="uq_part_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship back to Part
    part: Mapped["Part"] = relationship("Part", back_populates="alias_entries")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PartAlias part_id={self.part_id} alias={self.alias!r}>"
