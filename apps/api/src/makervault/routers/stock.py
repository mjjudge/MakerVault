"""Stock items API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.container import Container
from makervault.models.location import Location
from makervault.models.part import Part
from makervault.models.stock_item import StockItem
from makervault.schemas.stock_item import (
    BulkMoveRequest,
    BulkMoveResponse,
    StockItemCreate,
    StockItemListResponse,
    StockItemResponse,
    StockItemUpdate,
)

router = APIRouter(prefix="/stock", tags=["stock"])


async def _build_placement_lookups(
    items: list[StockItem], db: AsyncSession
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (location_names, container_names) dicts keyed by str(id)."""
    location_ids = {item.location_id for item in items if item.location_id}
    container_ids = {item.container_id for item in items if item.container_id}

    location_names: dict[str, str] = {}
    if location_ids:
        locs = (
            await db.execute(
                select(Location).where(Location.id.in_(location_ids))
            )
        ).scalars().all()
        location_names = {str(loc.id): loc.name for loc in locs}

    container_names: dict[str, str] = {}
    if container_ids:
        ctrs = (
            await db.execute(
                select(Container).where(Container.id.in_(container_ids))
            )
        ).scalars().all()
        container_names = {str(ctr.id): ctr.name for ctr in ctrs}

    return location_names, container_names


def _enrich(
    item: StockItem,
    location_names: dict[str, str],
    container_names: dict[str, str],
) -> StockItemResponse:
    data = {
        c.key: getattr(item, c.key)
        for c in item.__table__.columns
    }
    data["location_name"] = location_names.get(str(item.location_id)) if item.location_id else None
    data["container_name"] = container_names.get(str(item.container_id)) if item.container_id else None
    return StockItemResponse.model_validate(data)


@router.get("", response_model=StockItemListResponse, summary="List stock items")
async def list_stock(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    part_id: uuid.UUID | None = Query(default=None),
    location_id: uuid.UUID | None = Query(default=None),
    container_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> StockItemListResponse:
    query = select(StockItem)
    count_query = select(func.count()).select_from(StockItem)

    filters = []
    if part_id is not None:
        filters.append(StockItem.part_id == part_id)
    if location_id is not None:
        filters.append(StockItem.location_id == location_id)
    if container_id is not None:
        filters.append(StockItem.container_id == container_id)
    if status is not None:
        filters.append(StockItem.status == status)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(StockItem.created_at.desc()).offset(skip).limit(limit))
    items = result.scalars().all()

    location_names, container_names = await _build_placement_lookups(items, db)
    return StockItemListResponse(
        items=[_enrich(s, location_names, container_names) for s in items],
        total=total,
    )


@router.post(
    "",
    response_model=StockItemResponse,
    status_code=201,
    summary="Create a stock item",
)
async def create_stock_item(
    body: StockItemCreate,
    db: AsyncSession = Depends(get_db_session),
) -> StockItemResponse:
    # Validate part exists
    if await db.get(Part, body.part_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {body.part_id} not found.",
        )
    # Validate placement
    if body.location_id is not None and await db.get(Location, body.location_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {body.location_id} not found.",
        )
    if body.container_id is not None and await db.get(Container, body.container_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {body.container_id} not found.",
        )

    stock_item = StockItem(**body.model_dump())
    db.add(stock_item)
    await db.flush()
    await db.refresh(stock_item)
    loc_names, ctr_names = await _build_placement_lookups([stock_item], db)
    return _enrich(stock_item, loc_names, ctr_names)


@router.get(
    "/{stock_item_id}",
    response_model=StockItemResponse,
    summary="Get a stock item by ID",
)
async def get_stock_item(
    stock_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> StockItemResponse:
    item = await db.get(StockItem, stock_item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StockItem {stock_item_id} not found.",
        )
    loc_names, ctr_names = await _build_placement_lookups([item], db)
    return _enrich(item, loc_names, ctr_names)


@router.patch(
    "/{stock_item_id}",
    response_model=StockItemResponse,
    summary="Update a stock item",
)
async def update_stock_item(
    stock_item_id: uuid.UUID,
    body: StockItemUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> StockItemResponse:
    item = await db.get(StockItem, stock_item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StockItem {stock_item_id} not found.",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(item, field, value)
    await db.flush()
    await db.refresh(item)
    loc_names, ctr_names = await _build_placement_lookups([item], db)
    return _enrich(item, loc_names, ctr_names)


@router.delete(
    "/{stock_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stock item",
)
async def delete_stock_item(
    stock_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    item = await db.get(StockItem, stock_item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StockItem {stock_item_id} not found.",
        )
    await db.delete(item)


@router.post(
    "/bulk-move",
    response_model=BulkMoveResponse,
    summary="Move multiple stock items to a new location or container",
)
async def bulk_move_stock(
    body: BulkMoveRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkMoveResponse:
    """Relocate a batch of stock items in a single request.

    All items in ``stock_item_ids`` are moved to the supplied
    ``location_id`` or ``container_id``.  Items that cannot be found are
    reported in the ``not_found`` list; the rest are updated atomically.
    """
    # Validate the destination exists
    if body.location_id is not None:
        if await db.get(Location, body.location_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {body.location_id} not found.",
            )
    if body.container_id is not None:
        if await db.get(Container, body.container_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {body.container_id} not found.",
            )

    moved = 0
    not_found: list[str] = []

    for item_id in body.stock_item_ids:
        item = await db.get(StockItem, item_id)
        if item is None:
            not_found.append(str(item_id))
            continue
        item.location_id = body.location_id
        item.container_id = body.container_id
        moved += 1

    await db.flush()
    return BulkMoveResponse(moved=moved, not_found=not_found)
