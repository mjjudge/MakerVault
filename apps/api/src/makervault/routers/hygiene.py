"""Hygiene dashboard API router (Epic 15).

Endpoints
---------
GET  /hygiene/dashboard          — inventory hygiene overview
POST /parts/{part_id}/merge      — merge a source part into a canonical target
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.part import Part
from makervault.models.part_alias import PartAlias
from makervault.models.part_document import PartDocument
from makervault.models.project_part import ProjectPart
from makervault.models.stock_item import StockItem
from makervault.schemas.hygiene import (
    DuplicateGroup,
    HygieneDashboard,
    HygienePartSummary,
    MergeRequest,
    MergeResponse,
    SplitStockPart,
)

router = APIRouter(tags=["hygiene"])

# Status values that indicate stock is no longer physically present
_INACTIVE_STOCK_STATUSES = ("consumed", "missing", "damaged")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _part_summary(row: Part) -> HygienePartSummary:
    return HygienePartSummary(
        id=row.id,
        part_code=row.part_code,
        name=row.name,
        status=row.status,
    )


async def _fetch_part(db: AsyncSession, part_id: uuid.UUID) -> Part | None:
    """Fetch a Part by ID using an explicit SELECT (SQLite-compatible)."""
    result = await db.execute(select(Part).where(Part.id == part_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /hygiene/dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/hygiene/dashboard",
    response_model=HygieneDashboard,
    summary="Inventory hygiene dashboard",
)
async def hygiene_dashboard(
    db: AsyncSession = Depends(get_db_session),
) -> HygieneDashboard:
    """Return an overview of inventory hygiene issues:

    * Parts that have no linked documents
    * Parts that have no aliases (both Part.aliases array and PartAlias rows)
    * Parts that have no capabilities (array) or capabilities_json
    * Parts whose active stock is spread across more than one placement
    * Groups of potential duplicate parts
    """
    # ------------------------------------------------------------------
    # Load all active parts
    # ------------------------------------------------------------------
    parts_result = await db.execute(
        select(Part).where(Part.is_active.is_(True)).order_by(Part.name)  # noqa: E712
    )
    all_parts: list[Part] = parts_result.scalars().all()

    if not all_parts:
        return HygieneDashboard(
            parts_missing_documents=[],
            parts_missing_aliases=[],
            parts_missing_capabilities=[],
            split_stock_parts=[],
            duplicate_groups=[],
        )

    part_ids = [p.id for p in all_parts]

    # ------------------------------------------------------------------
    # Parts that HAVE at least one document link
    # ------------------------------------------------------------------
    docs_result = await db.execute(
        select(distinct(PartDocument.part_id)).where(
            PartDocument.part_id.in_(part_ids)
        )
    )
    parts_with_docs: set = {row[0] for row in docs_result.fetchall()}

    # ------------------------------------------------------------------
    # Parts that HAVE at least one alias row
    # ------------------------------------------------------------------
    alias_result = await db.execute(
        select(distinct(PartAlias.part_id)).where(
            PartAlias.part_id.in_(part_ids)
        )
    )
    parts_with_alias_rows: set = {row[0] for row in alias_result.fetchall()}

    # ------------------------------------------------------------------
    # Build output lists
    # ------------------------------------------------------------------
    missing_documents: list[HygienePartSummary] = []
    missing_aliases: list[HygienePartSummary] = []
    missing_capabilities: list[HygienePartSummary] = []

    for p in all_parts:
        # Compare by string so UUID / TEXT variants match across backends
        pid_str = str(p.id)
        has_doc = any(str(x) == pid_str for x in parts_with_docs)
        has_alias = any(str(x) == pid_str for x in parts_with_alias_rows) or bool(
            p.aliases
        )

        if not has_doc:
            missing_documents.append(_part_summary(p))
        if not has_alias:
            missing_aliases.append(_part_summary(p))
        if not p.capabilities and not p.capabilities_json:
            missing_capabilities.append(_part_summary(p))

    # ------------------------------------------------------------------
    # Split stock — parts with active stock in more than one placement
    # ------------------------------------------------------------------
    stock_result = await db.execute(
        select(StockItem).where(
            StockItem.part_id.in_(part_ids),
            StockItem.status.notin_(_INACTIVE_STOCK_STATUSES),
        )
    )
    stock_items: list[StockItem] = stock_result.scalars().all()

    # Group stock items by part_id
    stock_by_part: dict[str, list[StockItem]] = {}
    for s in stock_items:
        stock_by_part.setdefault(str(s.part_id), []).append(s)

    split_stock: list[SplitStockPart] = []
    part_by_id: dict[str, Part] = {str(p.id): p for p in all_parts}

    for part_id_str, items in stock_by_part.items():
        placements: dict[str, str] = {}
        for s in items:
            if s.location_id:
                placements[f"loc:{s.location_id}"] = str(s.location_id)
            elif s.container_id:
                placements[f"ctr:{s.container_id}"] = str(s.container_id)
        if len(placements) > 1:
            p = part_by_id[part_id_str]
            split_stock.append(
                SplitStockPart(
                    id=p.id,
                    part_code=p.part_code,
                    name=p.name,
                    status=p.status,
                    location_count=len(placements),
                    locations=list(placements.values()),
                )
            )

    # ------------------------------------------------------------------
    # Duplicate groups (same logic as GET /parts/duplicates)
    # ------------------------------------------------------------------
    name_groups: dict[str, list[Part]] = {}
    mpn_groups: dict[str, list[Part]] = {}
    for p in all_parts:
        name_groups.setdefault(p.name.strip().lower(), []).append(p)
        if p.manufacturer_part_number:
            mpn_groups.setdefault(
                p.manufacturer_part_number.strip().lower(), []
            ).append(p)

    dup_groups: list[DuplicateGroup] = []
    seen_ids: set[frozenset[str]] = set()
    for key, parts in {**name_groups, **mpn_groups}.items():
        if len(parts) < 2:
            continue
        ids = frozenset(str(p.id) for p in parts)
        if ids in seen_ids:
            continue
        seen_ids.add(ids)
        reason = (
            "same_name"
            if key in name_groups and len(name_groups.get(key, [])) >= 2
            else "same_mpn"
        )
        dup_groups.append(
            DuplicateGroup(
                reason=reason,
                parts=[
                    {
                        "id": str(p.id),
                        "part_code": p.part_code,
                        "name": p.name,
                        "manufacturer": p.manufacturer,
                        "manufacturer_part_number": p.manufacturer_part_number,
                        "status": p.status,
                    }
                    for p in parts
                ],
            )
        )

    return HygieneDashboard(
        parts_missing_documents=missing_documents,
        parts_missing_aliases=missing_aliases,
        parts_missing_capabilities=missing_capabilities,
        split_stock_parts=split_stock,
        duplicate_groups=dup_groups,
    )


# ---------------------------------------------------------------------------
# POST /parts/{part_id}/merge
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/merge",
    response_model=MergeResponse,
    summary="Merge a part into a canonical target part",
)
async def merge_part(
    part_id: uuid.UUID,
    body: MergeRequest,
    db: AsyncSession = Depends(get_db_session),
) -> MergeResponse:
    """Merge the **source** part (*part_id*) into the **target** part
    (*body.target_part_id*), then archive the source.

    The following child records are re-parented from source to target:

    * **StockItem** rows — placement and quantity are preserved
    * **PartDocument** links — duplicates (same document_id) are skipped
    * **PartAlias** rows — duplicates (same alias value) are skipped
    * **ProjectPart** rows — if the target already has an entry for the same
      project, the source entry is deleted; otherwise it is re-parented

    After the merge the source part is archived (``status='archived'``,
    ``is_active=False``).  It is **not** deleted so that audit history is
    preserved.
    """
    source_id = part_id
    target_id = body.target_part_id

    if source_id == target_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Source and target parts must be different.",
        )

    source = await _fetch_part(db, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source part {source_id} not found.",
        )
    target = await _fetch_part(db, target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target part {target_id} not found.",
        )

    # ------------------------------------------------------------------
    # Move stock items
    # ------------------------------------------------------------------
    stock_result = await db.execute(
        select(StockItem).where(StockItem.part_id == source_id)
    )
    stock_items: list[StockItem] = stock_result.scalars().all()
    for item in stock_items:
        item.part_id = target_id
    stock_moved = len(stock_items)

    # ------------------------------------------------------------------
    # Move document links (skip if target already has the same document)
    # ------------------------------------------------------------------
    src_doc_result = await db.execute(
        select(PartDocument).where(PartDocument.part_id == source_id)
    )
    src_doc_links: list[PartDocument] = src_doc_result.scalars().all()

    tgt_doc_result = await db.execute(
        select(PartDocument).where(PartDocument.part_id == target_id)
    )
    existing_doc_ids: set[str] = {
        str(row.document_id) for row in tgt_doc_result.scalars().all()
    }

    docs_moved = 0
    for link in src_doc_links:
        if str(link.document_id) in existing_doc_ids:
            await db.delete(link)
        else:
            link.part_id = target_id
            docs_moved += 1

    # ------------------------------------------------------------------
    # Move alias entries (skip if target already has the same alias value)
    # ------------------------------------------------------------------
    src_alias_result = await db.execute(
        select(PartAlias).where(PartAlias.part_id == source_id)
    )
    src_aliases: list[PartAlias] = src_alias_result.scalars().all()

    tgt_alias_result = await db.execute(
        select(PartAlias).where(PartAlias.part_id == target_id)
    )
    existing_alias_values: set[str] = {
        row.alias.lower() for row in tgt_alias_result.scalars().all()
    }

    aliases_moved = 0
    for alias_row in src_aliases:
        if alias_row.alias.lower() in existing_alias_values:
            await db.delete(alias_row)
        else:
            alias_row.part_id = target_id
            aliases_moved += 1

    # ------------------------------------------------------------------
    # Move project parts
    # ------------------------------------------------------------------
    src_pp_result = await db.execute(
        select(ProjectPart).where(ProjectPart.part_id == source_id)
    )
    src_project_parts: list[ProjectPart] = src_pp_result.scalars().all()

    tgt_pp_result = await db.execute(
        select(ProjectPart).where(ProjectPart.part_id == target_id)
    )
    existing_project_ids: set[str] = {
        str(row.project_id) for row in tgt_pp_result.scalars().all()
    }

    pp_moved = 0
    for pp in src_project_parts:
        if str(pp.project_id) in existing_project_ids:
            await db.delete(pp)
        else:
            pp.part_id = target_id
            pp_moved += 1

    # ------------------------------------------------------------------
    # Archive the source part
    # ------------------------------------------------------------------
    source.status = "archived"
    source.is_active = False

    await db.flush()

    return MergeResponse(
        target_part_id=target_id,
        source_part_id=source_id,
        stock_items_moved=stock_moved,
        document_links_moved=docs_moved,
        aliases_moved=aliases_moved,
        project_parts_moved=pp_moved,
        source_archived=True,
    )


