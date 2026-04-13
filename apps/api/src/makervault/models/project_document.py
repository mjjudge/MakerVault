"""ProjectDocument ORM model.

Join table linking a Document to a Project.
Useful for wiring notes, design sketches, photos, AI plans, etc.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

PROJECT_DOCUMENT_RELATIONSHIP_VALUES = (
    "wiring_note",
    "photo",
    "setup_instruction",
    "design_sketch",
    "ai_plan",
    "reference",
    "other",
)


class ProjectDocument(TimestampMixin, Base):
    """Associates a Document with a Project."""

    __tablename__ = "project_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
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
            *PROJECT_DOCUMENT_RELATIONSHIP_VALUES,
            name="project_document_relationship_enum",
            create_type=True,
        ),
        nullable=False,
        default="other",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="document_links"
    )
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="project_links"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProjectDocument project={self.project_id} document={self.document_id}>"
