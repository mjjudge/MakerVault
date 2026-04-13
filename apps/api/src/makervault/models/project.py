"""Project ORM model.

Full project entity including BOM support (Epic 7).
"""

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

PROJECT_STATUS_VALUES = ("active", "completed", "on_hold", "archived")


class Project(TimestampMixin, Base):
    """A planned or completed build project."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    document_links: Mapped[list["ProjectDocument"]] = relationship(  # noqa: F821
        "ProjectDocument", back_populates="project", cascade="all, delete-orphan"
    )
    project_parts: Mapped[list["ProjectPart"]] = relationship(  # noqa: F821
        "ProjectPart", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project id={self.id} name={self.name!r}>"
