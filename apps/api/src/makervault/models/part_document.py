"""PartDocument ORM model.

Join table linking a Document to a Part.
One Document can be linked to multiple Parts and vice versa.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

PART_DOCUMENT_RELATIONSHIP_VALUES = (
    "primary_datasheet",
    "manual",
    "pinout",
    "schematic",
    "supporting_reference",
    "other",
)


class PartDocument(TimestampMixin, Base):
    """Associates a Document with a Part."""

    __tablename__ = "part_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(
        Enum(
            *PART_DOCUMENT_RELATIONSHIP_VALUES,
            name="part_document_relationship_enum",
            create_type=True,
        ),
        nullable=False,
        default="other",
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="document_links")  # noqa: F821
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="part_links"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PartDocument part={self.part_id} document={self.document_id}>"
