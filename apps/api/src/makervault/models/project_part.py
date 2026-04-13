"""ProjectPart ORM model — Bill of Materials entry.

Each ProjectPart links a Part to a Project with a required quantity,
forming the BOM (Bill of Materials) for that project.
"""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class ProjectPart(TimestampMixin, Base):
    """A single BOM entry: one part required by one project."""

    __tablename__ = "project_parts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_required: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("1")
    )
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="project_parts"
    )
    part: Mapped["Part"] = relationship(  # noqa: F821
        "Part", back_populates="project_parts"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectPart project={self.project_id} part={self.part_id} qty={self.quantity_required}>"
