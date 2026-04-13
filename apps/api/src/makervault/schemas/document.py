"""Pydantic schemas for Document, PartDocument, StockItemDocument, and ProjectDocument."""

import uuid
from datetime import datetime

from pydantic import Field

from makervault.models.document import DOCUMENT_SOURCE_TYPE_VALUES, DOCUMENT_TYPE_VALUES
from makervault.models.part_document import PART_DOCUMENT_RELATIONSHIP_VALUES
from makervault.models.project_document import PROJECT_DOCUMENT_RELATIONSHIP_VALUES
from makervault.schemas.base import BaseSchema


# ---------------------------------------------------------------------------
# Document schemas
# ---------------------------------------------------------------------------


class DocumentCreate(BaseSchema):
    title: str = Field(..., min_length=1, max_length=500)
    document_type: str = Field(
        default="other",
        pattern=f"^({'|'.join(DOCUMENT_TYPE_VALUES)})$",
    )
    source_type: str = Field(
        default="uploaded",
        pattern=f"^({'|'.join(DOCUMENT_SOURCE_TYPE_VALUES)})$",
    )
    source_url: str | None = None
    version_label: str | None = None
    notes: str | None = None


class DocumentUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    document_type: str | None = Field(
        default=None,
        pattern=f"^({'|'.join(DOCUMENT_TYPE_VALUES)})$",
    )
    source_url: str | None = None
    version_label: str | None = None
    text_extracted: str | None = None
    summary: str | None = None
    notes: str | None = None


class DocumentResponse(BaseSchema):
    id: uuid.UUID
    title: str
    document_type: str
    source_type: str
    source_url: str | None
    local_path: str | None
    mime_type: str | None
    checksum: str | None
    file_size_bytes: int | None
    text_extracted: str | None
    summary: str | None
    version_label: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseSchema):
    items: list[DocumentResponse]
    total: int


# ---------------------------------------------------------------------------
# PartDocument schemas
# ---------------------------------------------------------------------------


class PartDocumentCreate(BaseSchema):
    document_id: uuid.UUID
    relationship_type: str = Field(
        default="other",
        pattern=f"^({'|'.join(PART_DOCUMENT_RELATIONSHIP_VALUES)})$",
    )
    is_primary: bool = False
    notes: str | None = None


class PartDocumentResponse(BaseSchema):
    id: uuid.UUID
    part_id: uuid.UUID
    document_id: uuid.UUID
    relationship_type: str
    is_primary: bool
    notes: str | None
    document: DocumentResponse
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# StockItemDocument schemas
# ---------------------------------------------------------------------------


class StockItemDocumentCreate(BaseSchema):
    document_id: uuid.UUID
    notes: str | None = None


class StockItemDocumentResponse(BaseSchema):
    id: uuid.UUID
    stock_item_id: uuid.UUID
    document_id: uuid.UUID
    notes: str | None
    document: DocumentResponse
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# ProjectDocument schemas
# ---------------------------------------------------------------------------


class ProjectDocumentCreate(BaseSchema):
    document_id: uuid.UUID
    relationship_type: str = Field(
        default="other",
        pattern=f"^({'|'.join(PROJECT_DOCUMENT_RELATIONSHIP_VALUES)})$",
    )
    notes: str | None = None


class ProjectDocumentResponse(BaseSchema):
    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    relationship_type: str
    notes: str | None
    document: DocumentResponse
    created_at: datetime
    updated_at: datetime
