"""StockItemDocument ORM model.

Join table linking a Document to a StockItem.
Useful for receipts, condition photos, test reports, etc.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid


class StockItemDocument(TimestampMixin, Base):
    """Associates a Document with a StockItem."""

    __tablename__ = "stock_item_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    stock_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stock_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    stock_item: Mapped["StockItem"] = relationship(  # noqa: F821
        "StockItem", back_populates="document_links"
    )
    document: Mapped["Document"] = relationship(  # noqa: F821
        "Document", back_populates="stock_item_links"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StockItemDocument stock_item={self.stock_item_id} document={self.document_id}>"
