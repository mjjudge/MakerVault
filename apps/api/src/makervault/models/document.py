"""Document ORM model.

A Document is any locally preserved reference material: a PDF datasheet,
pinout image, manual, saved vendor page, receipt, wiring note, or setup guide.

Documents are first-class entities linked to Parts, StockItems, and Projects
via join tables (PartDocument, StockItemDocument, ProjectDocument).
"""

import uuid

from sqlalchemy import BigInteger, Enum, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

DOCUMENT_TYPE_VALUES = (
    "datasheet",
    "manual",
    "pinout",
    "schematic",
    "vendor_page",
    "receipt",
    "photo",
    "project_note",
    "setup_note",
    "firmware_note",
    "other",
)

DOCUMENT_SOURCE_TYPE_VALUES = (
    "uploaded",
    "captured_from_web",
    "manual_note",
    "generated_summary",
)


class Document(TimestampMixin, Base):
    """A locally preserved reference document with rich metadata."""

    __tablename__ = "documents"

    __table_args__ = (
        Index("ix_documents_checksum", "checksum"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(
        Enum(*DOCUMENT_TYPE_VALUES, name="document_type_enum", create_type=True),
        nullable=False,
        default="other",
    )
    source_type: Mapped[str] = mapped_column(
        Enum(*DOCUMENT_SOURCE_TYPE_VALUES, name="document_source_type_enum", create_type=True),
        nullable=False,
        default="uploaded",
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File storage
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Content
    text_extracted: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships (via join tables)
    part_links: Mapped[list["PartDocument"]] = relationship(  # noqa: F821
        "PartDocument", back_populates="document", cascade="all, delete-orphan"
    )
    stock_item_links: Mapped[list["StockItemDocument"]] = relationship(  # noqa: F821
        "StockItemDocument", back_populates="document", cascade="all, delete-orphan"
    )
    project_links: Mapped[list["ProjectDocument"]] = relationship(  # noqa: F821
        "ProjectDocument", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document id={self.id} title={self.title!r}>"
