"""Part ORM model.

A Part is the canonical definition of a type of component, board, module,
tool, or device. It describes *what something is* in the abstract — not a
specific physical unit you own.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

# Enumerations ----------------------------------------------------------------

PART_KIND_VALUES = (
    "component",
    "board",
    "module",
    "device",
    "tool",
    "consumable",
    "material",
    "accessory",
    "cable",
    "power_supply",
    "enclosure",
)

PART_STATUS_VALUES = ("active", "draft", "archived")

PART_PROVENANCE_VALUES = ("manual", "ai_enriched", "imported")


class Part(TimestampMixin, Base):
    """Abstract definition of a part type."""

    __tablename__ = "parts"

    __table_args__ = (
        Index("ix_parts_search_text", "search_text", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    part_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    part_kind: Mapped[str | None] = mapped_column(
        Enum(*PART_KIND_VALUES, name="part_kind_enum", create_type=True),
        nullable=True,
    )
    manufacturer: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer_part_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_unit: Mapped[str] = mapped_column(Text, nullable=False, default="pcs")
    package_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    spec_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    search_text: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    is_consumable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_serialised: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hazardous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    status: Mapped[str] = mapped_column(
        Enum(*PART_STATUS_VALUES, name="part_status_enum", create_type=True),
        nullable=False,
        default="draft",
    )
    identification_confidence: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provenance: Mapped[str | None] = mapped_column(
        Enum(*PART_PROVENANCE_VALUES, name="part_provenance_enum", create_type=True),
        nullable=True,
        default="manual",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="parts"
    )
    stock_items: Mapped[list["StockItem"]] = relationship(  # noqa: F821
        "StockItem", back_populates="part"
    )
    document_links: Mapped[list["PartDocument"]] = relationship(  # noqa: F821
        "PartDocument", back_populates="part", cascade="all, delete-orphan"
    )
    project_parts: Mapped[list["ProjectPart"]] = relationship(  # noqa: F821
        "ProjectPart", back_populates="part"
    )
    alias_entries: Mapped[list["PartAlias"]] = relationship(  # noqa: F821
        "PartAlias", back_populates="part", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Part id={self.id} part_code={self.part_code!r} name={self.name!r}>"
