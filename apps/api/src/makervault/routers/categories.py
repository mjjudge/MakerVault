"""Categories API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.category import Category
from makervault.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse, summary="List categories")
async def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> CategoryListResponse:
    total_result = await db.execute(select(func.count()).select_from(Category))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Category).order_by(Category.name).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return CategoryListResponse(
        items=[CategoryResponse.model_validate(c) for c in items], total=total
    )


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category",
)
async def create_category(
    body: CategoryCreate,
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    if body.parent_category_id is not None:
        parent = await db.get(Category, body.parent_category_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent category {body.parent_category_id} not found.",
            )
    category = Category(**body.model_dump())
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Get a category by ID",
)
async def get_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category {category_id} not found.",
        )
    return CategoryResponse.model_validate(category)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category",
)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category {category_id} not found.",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(category, field, value)
    await db.flush()
    await db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category",
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    category = await db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category {category_id} not found.",
        )
    await db.delete(category)
