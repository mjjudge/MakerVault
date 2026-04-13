"""Part aliases API router.

Manages PartAlias rows (the normalised alias store) and keeps the
denormalised Part.aliases array in sync after every mutation.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.part import Part
from makervault.models.part_alias import PartAlias
from makervault.schemas.part_alias import PartAliasCreate, PartAliasResponse

router = APIRouter(prefix="/parts/{part_id}/aliases", tags=["part-aliases"])


async def _get_part_or_404(part_id: uuid.UUID, db: AsyncSession) -> Part:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found.",
        )
    return part


async def _sync_aliases_array(part: Part, db: AsyncSession) -> None:
    """Rebuild the denormalised Part.aliases array from PartAlias rows.

    On PostgreSQL the ORM attribute is set directly (native ARRAY type).
    On SQLite (used in tests) a raw SQL UPDATE stores a comma-separated
    string, since SQLite cannot bind Python lists to a TEXT column.
    """
    result = await db.execute(
        select(PartAlias.alias)
        .where(PartAlias.part_id == part.id)
        .order_by(PartAlias.alias)
    )
    aliases = result.scalars().all()

    try:
        dialect_name = db.sync_session.get_bind().dialect.name
    except Exception:
        dialect_name = "postgresql"

    if dialect_name == "postgresql":
        part.aliases = list(aliases) if aliases else None
    else:
        # SQLite: persist as a comma-separated string via raw SQL so that
        # CAST(aliases AS TEXT) LIKE searches still work.
        alias_str = ",".join(aliases) if aliases else None
        await db.execute(
            text("UPDATE parts SET aliases = :a WHERE id = :id"),
            {"a": alias_str, "id": part.id.hex},
        )
        # Expire the cached ORM object so the next read re-fetches from DB.
        db.sync_session.expire(part)


@router.get("", response_model=list[PartAliasResponse], summary="List aliases for a part")
async def list_aliases(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> list[PartAliasResponse]:
    await _get_part_or_404(part_id, db)
    result = await db.execute(
        select(PartAlias)
        .where(PartAlias.part_id == part_id)
        .order_by(PartAlias.alias)
    )
    rows = result.scalars().all()
    return [PartAliasResponse.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=PartAliasResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an alias to a part",
)
async def create_alias(
    part_id: uuid.UUID,
    body: PartAliasCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PartAliasResponse:
    part = await _get_part_or_404(part_id, db)

    # Check uniqueness
    existing = await db.execute(
        select(PartAlias).where(
            PartAlias.part_id == part_id,
            PartAlias.alias == body.alias,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias '{body.alias}' already exists for this part.",
        )

    alias_row = PartAlias(part_id=part_id, alias=body.alias, notes=body.notes)
    db.add(alias_row)
    await db.flush()
    await db.refresh(alias_row)

    await _sync_aliases_array(part, db)
    await db.flush()

    return PartAliasResponse.model_validate(alias_row)


@router.delete(
    "/{alias_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an alias from a part",
)
async def delete_alias(
    part_id: uuid.UUID,
    alias_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    part = await _get_part_or_404(part_id, db)

    alias_row = await db.get(PartAlias, alias_id)
    if alias_row is None or alias_row.part_id != part_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alias {alias_id} not found for part {part_id}.",
        )

    await db.delete(alias_row)
    await db.flush()

    await _sync_aliases_array(part, db)
    await db.flush()
