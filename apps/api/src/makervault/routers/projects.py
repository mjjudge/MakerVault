"""Projects API router — CRUD + BOM endpoints + availability calculation."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from makervault.database import get_db_session
from makervault.models.part import Part
from makervault.models.project import Project
from makervault.models.project_part import ProjectPart
from makervault.models.stock_item import StockItem
from makervault.schemas.project import (
    BOMAvailabilityResponse,
    BOMEntryAvailability,
    ProjectCreate,
    ProjectListResponse,
    ProjectPartCreate,
    ProjectPartResponse,
    ProjectPartUpdate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found.",
        )
    return project


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=ProjectListResponse, summary="List / search projects")
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(default=None, description="Search in name or description"),
    project_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db_session),
) -> ProjectListResponse:
    query = select(Project)
    count_query = select(func.count()).select_from(Project)

    filters = []
    if q:
        like = f"%{q}%"
        filters.append(
            Project.name.ilike(like) | Project.description.ilike(like)
        )
    if project_status is not None:
        filters.append(Project.status == project_status)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in items], total=total
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = Project(**body.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project by ID",
)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = await _get_project_or_404(project_id, db)
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = await _get_project_or_404(project_id, db)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    project = await _get_project_or_404(project_id, db)
    await db.delete(project)


# ---------------------------------------------------------------------------
# BOM (ProjectPart) endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/parts",
    response_model=list[ProjectPartResponse],
    summary="List BOM entries for a project",
)
async def list_project_parts(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[ProjectPartResponse]:
    await _get_project_or_404(project_id, db)
    result = await db.execute(
        select(ProjectPart)
        .where(ProjectPart.project_id == project_id)
        .options(selectinload(ProjectPart.part))
        .order_by(ProjectPart.created_at)
    )
    entries = result.scalars().all()
    return [ProjectPartResponse.model_validate(e) for e in entries]


@router.post(
    "/{project_id}/parts",
    response_model=ProjectPartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a part to a project BOM",
)
async def add_project_part(
    project_id: uuid.UUID,
    body: ProjectPartCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectPartResponse:
    await _get_project_or_404(project_id, db)

    part = await db.get(Part, body.part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {body.part_id} not found.",
        )

    entry = ProjectPart(
        project_id=project_id,
        part_id=body.part_id,
        quantity_required=body.quantity_required,
        unit=body.unit,
        notes=body.notes,
    )
    db.add(entry)
    await db.flush()

    result = await db.execute(
        select(ProjectPart)
        .where(ProjectPart.id == entry.id)
        .options(selectinload(ProjectPart.part))
    )
    entry = result.scalar_one()
    return ProjectPartResponse.model_validate(entry)


@router.patch(
    "/{project_id}/parts/{entry_id}",
    response_model=ProjectPartResponse,
    summary="Update a BOM entry",
)
async def update_project_part(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: ProjectPartUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectPartResponse:
    await _get_project_or_404(project_id, db)

    entry = await db.get(ProjectPart, entry_id)
    if entry is None or entry.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM entry {entry_id} not found for project {project_id}.",
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)
    await db.flush()

    result = await db.execute(
        select(ProjectPart)
        .where(ProjectPart.id == entry_id)
        .options(selectinload(ProjectPart.part))
    )
    entry = result.scalar_one()
    return ProjectPartResponse.model_validate(entry)


@router.delete(
    "/{project_id}/parts/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a part from a project BOM",
)
async def remove_project_part(
    project_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _get_project_or_404(project_id, db)

    entry = await db.get(ProjectPart, entry_id)
    if entry is None or entry.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BOM entry {entry_id} not found for project {project_id}.",
        )
    await db.delete(entry)


# ---------------------------------------------------------------------------
# BOM availability
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/availability",
    response_model=BOMAvailabilityResponse,
    summary="Check BOM availability against current stock",
)
async def get_bom_availability(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> BOMAvailabilityResponse:
    await _get_project_or_404(project_id, db)

    result = await db.execute(
        select(ProjectPart)
        .where(ProjectPart.project_id == project_id)
        .options(selectinload(ProjectPart.part))
        .order_by(ProjectPart.created_at)
    )
    bom_entries = result.scalars().all()

    entries: list[BOMEntryAvailability] = []
    for entry in bom_entries:
        # Sum available stock for this part
        stock_result = await db.execute(
            select(func.coalesce(func.sum(StockItem.quantity), 0)).where(
                StockItem.part_id == entry.part_id,
                StockItem.status == "available",
            )
        )
        total_in_stock = Decimal(str(stock_result.scalar_one()))
        is_available = total_in_stock >= entry.quantity_required

        entries.append(
            BOMEntryAvailability(
                project_part_id=entry.id,
                part_id=entry.part_id,
                part_code=entry.part.part_code,
                part_name=entry.part.name,
                quantity_required=entry.quantity_required,
                total_in_stock=total_in_stock,
                is_available=is_available,
            )
        )

    all_available = all(e.is_available for e in entries)
    return BOMAvailabilityResponse(
        project_id=project_id,
        entries=entries,
        all_available=all_available,
    )
