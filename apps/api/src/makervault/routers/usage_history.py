"""Usage history API router.

Endpoints:
  GET  /usage         — list events (filterable by stock_item_id, project_id, part_id)
  POST /usage         — record a new lifecycle event
  GET  /usage/{id}    — fetch a single event
  DELETE /usage/{id}  — delete an event
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.part import Part
from makervault.models.project import Project
from makervault.models.stock_item import StockItem
from makervault.models.usage_history import UsageHistory
from makervault.schemas.usage_history import (
    UsageHistoryCreate,
    UsageHistoryListResponse,
    UsageHistoryResponse,
)

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageHistoryListResponse, summary="List usage history events")
async def list_usage_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    stock_item_id: uuid.UUID | None = Query(default=None),
    project_id: uuid.UUID | None = Query(default=None),
    part_id: uuid.UUID | None = Query(default=None),
    action_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> UsageHistoryListResponse:
    query = select(UsageHistory)
    count_query = select(func.count()).select_from(UsageHistory)

    filters = []
    if stock_item_id is not None:
        filters.append(UsageHistory.stock_item_id == stock_item_id)
    if project_id is not None:
        filters.append(UsageHistory.project_id == project_id)
    if part_id is not None:
        filters.append(UsageHistory.part_id == part_id)
    if action_type is not None:
        filters.append(UsageHistory.action_type == action_type)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(
        query.order_by(UsageHistory.used_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()

    return UsageHistoryListResponse(items=list(items), total=total)


@router.post(
    "",
    response_model=UsageHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a usage history event",
)
async def create_usage_event(
    body: UsageHistoryCreate,
    db: AsyncSession = Depends(get_db_session),
) -> UsageHistoryResponse:
    # Validate FK references when provided
    if body.stock_item_id is not None:
        if await db.get(StockItem, body.stock_item_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"StockItem {body.stock_item_id} not found.",
            )

    if body.project_id is not None:
        if await db.get(Project, body.project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {body.project_id} not found.",
            )

    if body.part_id is not None:
        if await db.get(Part, body.part_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Part {body.part_id} not found.",
            )

    data = body.model_dump()

    # Default used_at to now if not supplied
    if data.get("used_at") is None:
        data["used_at"] = datetime.now(timezone.utc)

    # Auto-populate part_id from the stock item when not explicitly provided
    if data.get("part_id") is None and body.stock_item_id is not None:
        stock_item = await db.get(StockItem, body.stock_item_id)
        if stock_item is not None:
            data["part_id"] = stock_item.part_id

    event = UsageHistory(**data)
    db.add(event)

    # Apply quantity_delta to the StockItem when relevant
    if (
        body.stock_item_id is not None
        and body.quantity_delta is not None
        and body.quantity_delta != 0
    ):
        stock_item = await db.get(StockItem, body.stock_item_id)
        if stock_item is not None:
            new_qty = float(stock_item.quantity) + body.quantity_delta
            stock_item.quantity = max(new_qty, 0)

    await db.flush()
    await db.refresh(event)
    return UsageHistoryResponse.model_validate(event)


@router.get(
    "/{event_id}",
    response_model=UsageHistoryResponse,
    summary="Get a usage history event by ID",
)
async def get_usage_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> UsageHistoryResponse:
    event = await db.get(UsageHistory, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UsageHistory event {event_id} not found.",
        )
    return UsageHistoryResponse.model_validate(event)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a usage history event",
)
async def delete_usage_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    event = await db.get(UsageHistory, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UsageHistory event {event_id} not found.",
        )
    await db.delete(event)
