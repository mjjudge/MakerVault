"""Documents API router.

Endpoints:
  POST   /documents/upload          — upload a file and create a Document record
  GET    /documents                  — list documents (with optional filters)
  GET    /documents/{id}             — get a document by ID
  PATCH  /documents/{id}             — update document metadata
  DELETE /documents/{id}             — delete a document and its stored file

  POST   /parts/{part_id}/documents          — link a document to a part
  GET    /parts/{part_id}/documents          — list documents for a part
  DELETE /parts/{part_id}/documents/{link_id} — remove a part-document link

  POST   /stock/{stock_item_id}/documents            — link a document to a stock item
  GET    /stock/{stock_item_id}/documents            — list documents for a stock item
  DELETE /stock/{stock_item_id}/documents/{link_id}  — remove a stock-item-document link

  POST   /projects/{project_id}/documents            — link a document to a project
  GET    /projects/{project_id}/documents            — list documents for a project
  DELETE /projects/{project_id}/documents/{link_id}  — remove a project-document link
"""

import mimetypes
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from makervault.config import get_settings, Settings
from makervault.database import get_db_session
from makervault.models.document import Document, DOCUMENT_TYPE_VALUES, DOCUMENT_SOURCE_TYPE_VALUES
from makervault.models.part import Part
from makervault.models.part_document import PartDocument, PART_DOCUMENT_RELATIONSHIP_VALUES
from makervault.models.project import Project
from makervault.models.project_document import ProjectDocument
from makervault.models.stock_item import StockItem
from makervault.models.stock_item_document import StockItemDocument
from makervault.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    PartDocumentCreate,
    PartDocumentResponse,
    ProjectDocumentCreate,
    ProjectDocumentResponse,
    StockItemDocumentCreate,
    StockItemDocumentResponse,
)
from makervault.services.document_store import delete_document_file, save_document

router = APIRouter(tags=["documents"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB


async def _get_document_or_404(doc_id: uuid.UUID, db: AsyncSession) -> Document:
    doc = await db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id} not found.")
    return doc


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/documents/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file and create a document record",
)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(default="other"),
    source_url: str | None = Form(default=None),
    version_label: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    if document_type not in DOCUMENT_TYPE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid document_type. Must be one of: {', '.join(DOCUMENT_TYPE_VALUES)}",
        )

    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {_MAX_UPLOAD_BYTES // (1024*1024)} MiB.",
        )

    doc_id = uuid.uuid4()
    original_filename = file.filename or "upload"

    # Detect MIME type — prefer the header, fall back to extension guess
    mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

    relative_path, checksum, file_size = save_document(
        settings.document_store_path, doc_id, original_filename, data
    )

    doc = Document(
        id=doc_id,
        title=title,
        document_type=document_type,
        source_type="uploaded",
        source_url=source_url,
        local_path=relative_path,
        mime_type=mime_type,
        checksum=checksum,
        file_size_bytes=file_size,
        version_label=version_label,
        notes=notes,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List documents",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    document_type: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search in title"),
    db: AsyncSession = Depends(get_db_session),
) -> DocumentListResponse:
    query = select(Document)
    count_query = select(func.count()).select_from(Document)

    filters = []
    if document_type is not None:
        filters.append(Document.document_type == document_type)
    if q:
        filters.append(Document.title.ilike(f"%{q}%"))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in items], total=total
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get a document by ID",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    doc = await _get_document_or_404(document_id, db)
    return DocumentResponse.model_validate(doc)


@router.patch(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Update document metadata",
)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    doc = await _get_document_or_404(document_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    await db.flush()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its stored file",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> None:
    doc = await _get_document_or_404(document_id, db)
    if doc.local_path:
        delete_document_file(settings.document_store_path, doc.local_path)
    await db.delete(doc)


# ---------------------------------------------------------------------------
# Part ↔ Document links
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/documents",
    response_model=PartDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a document to a part",
)
async def link_document_to_part(
    part_id: uuid.UUID,
    body: PartDocumentCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PartDocumentResponse:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"Part {part_id} not found.")
    doc = await _get_document_or_404(body.document_id, db)

    link = PartDocument(
        part_id=part_id,
        document_id=doc.id,
        relationship_type=body.relationship_type,
        is_primary=body.is_primary,
        notes=body.notes,
    )
    db.add(link)
    await db.flush()
    result = await db.execute(
        select(PartDocument)
        .where(PartDocument.id == link.id)
        .options(selectinload(PartDocument.document))
    )
    link = result.scalar_one()
    return PartDocumentResponse.model_validate(link)


@router.get(
    "/parts/{part_id}/documents",
    response_model=list[PartDocumentResponse],
    summary="List documents linked to a part",
)
async def list_part_documents(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[PartDocumentResponse]:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"Part {part_id} not found.")
    result = await db.execute(
        select(PartDocument)
        .where(PartDocument.part_id == part_id)
        .options(selectinload(PartDocument.document))
        .order_by(PartDocument.created_at.desc())
    )
    links = result.scalars().all()
    return [PartDocumentResponse.model_validate(l) for l in links]


@router.delete(
    "/parts/{part_id}/documents/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a part-document link",
)
async def unlink_document_from_part(
    part_id: uuid.UUID,
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    link = await db.get(PartDocument, link_id)
    if link is None or link.part_id != part_id:
        raise HTTPException(status_code=404, detail=f"Link {link_id} not found for part {part_id}.")
    await db.delete(link)


# ---------------------------------------------------------------------------
# StockItem ↔ Document links
# ---------------------------------------------------------------------------


@router.post(
    "/stock/{stock_item_id}/documents",
    response_model=StockItemDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a document to a stock item",
)
async def link_document_to_stock_item(
    stock_item_id: uuid.UUID,
    body: StockItemDocumentCreate,
    db: AsyncSession = Depends(get_db_session),
) -> StockItemDocumentResponse:
    item = await db.get(StockItem, stock_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"StockItem {stock_item_id} not found.")
    doc = await _get_document_or_404(body.document_id, db)

    link = StockItemDocument(
        stock_item_id=stock_item_id,
        document_id=doc.id,
        notes=body.notes,
    )
    db.add(link)
    await db.flush()
    result = await db.execute(
        select(StockItemDocument)
        .where(StockItemDocument.id == link.id)
        .options(selectinload(StockItemDocument.document))
    )
    link = result.scalar_one()
    return StockItemDocumentResponse.model_validate(link)


@router.get(
    "/stock/{stock_item_id}/documents",
    response_model=list[StockItemDocumentResponse],
    summary="List documents linked to a stock item",
)
async def list_stock_item_documents(
    stock_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[StockItemDocumentResponse]:
    item = await db.get(StockItem, stock_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"StockItem {stock_item_id} not found.")
    result = await db.execute(
        select(StockItemDocument)
        .where(StockItemDocument.stock_item_id == stock_item_id)
        .options(selectinload(StockItemDocument.document))
        .order_by(StockItemDocument.created_at.desc())
    )
    links = result.scalars().all()
    return [StockItemDocumentResponse.model_validate(l) for l in links]


@router.delete(
    "/stock/{stock_item_id}/documents/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a stock-item-document link",
)
async def unlink_document_from_stock_item(
    stock_item_id: uuid.UUID,
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    link = await db.get(StockItemDocument, link_id)
    if link is None or link.stock_item_id != stock_item_id:
        raise HTTPException(status_code=404, detail=f"Link {link_id} not found for stock item {stock_item_id}.")
    await db.delete(link)


# ---------------------------------------------------------------------------
# Project ↔ Document links
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/documents",
    response_model=ProjectDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Link a document to a project",
)
async def link_document_to_project(
    project_id: uuid.UUID,
    body: ProjectDocumentCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectDocumentResponse:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")
    doc = await _get_document_or_404(body.document_id, db)

    link = ProjectDocument(
        project_id=project_id,
        document_id=doc.id,
        relationship_type=body.relationship_type,
        notes=body.notes,
    )
    db.add(link)
    await db.flush()
    result = await db.execute(
        select(ProjectDocument)
        .where(ProjectDocument.id == link.id)
        .options(selectinload(ProjectDocument.document))
    )
    link = result.scalar_one()
    return ProjectDocumentResponse.model_validate(link)


@router.get(
    "/projects/{project_id}/documents",
    response_model=list[ProjectDocumentResponse],
    summary="List documents linked to a project",
)
async def list_project_documents(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ProjectDocumentResponse]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")
    result = await db.execute(
        select(ProjectDocument)
        .where(ProjectDocument.project_id == project_id)
        .options(selectinload(ProjectDocument.document))
        .order_by(ProjectDocument.created_at.desc())
    )
    links = result.scalars().all()
    return [ProjectDocumentResponse.model_validate(l) for l in links]


@router.delete(
    "/projects/{project_id}/documents/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a project-document link",
)
async def unlink_document_from_project(
    project_id: uuid.UUID,
    link_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    link = await db.get(ProjectDocument, link_id)
    if link is None or link.project_id != project_id:
        raise HTTPException(status_code=404, detail=f"Link {link_id} not found for project {project_id}.")
    await db.delete(link)
