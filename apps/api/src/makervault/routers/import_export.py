"""Import / export router — CSV ingestion and data export.

Supported operations
--------------------
GET  /api/import-export/parts/export       — download all parts as CSV
GET  /api/import-export/stock/export       — download all stock items as CSV
POST /api/import-export/parts/import       — upload a CSV file to create / update parts
POST /api/import-export/stock/import       — upload a CSV file to create stock items
GET  /api/import-export/parts/template     — download a blank parts CSV template
GET  /api/import-export/stock/template     — download a blank stock CSV template
"""

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.container import Container
from makervault.models.location import Location
from makervault.models.part import Part
from makervault.models.stock_item import StockItem, STOCK_STATUS_VALUES, STOCK_CONDITION_VALUES
from makervault.schemas.part import PartCreate, PartResponse
from makervault.schemas.stock_item import StockItemCreate, StockItemResponse

router = APIRouter(prefix="/import-export", tags=["import-export"])

# ---------------------------------------------------------------------------
# Helper — CSV response builder
# ---------------------------------------------------------------------------

def _csv_streaming_response(rows: list[dict[str, Any]], filename: str) -> StreamingResponse:
    """Return a StreamingResponse that delivers ``rows`` as a UTF-8 CSV download."""
    if not rows:
        output = io.StringIO()
        output.write("")
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _empty_csv_response(fieldnames: list[str], filename: str) -> StreamingResponse:
    """Return a CSV with only a header row (template download)."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

PARTS_EXPORT_FIELDS = [
    "part_code", "name", "short_description", "part_kind",
    "manufacturer", "manufacturer_part_number", "default_unit",
    "package_type", "spec_summary", "tags", "is_consumable",
    "is_serialised", "is_hazardous", "status", "notes",
]

STOCK_EXPORT_FIELDS = [
    "stock_item_id", "part_code", "part_name", "quantity", "unit",
    "status", "condition", "location_name", "container_name",
    "serial_number", "batch_code", "purchase_date", "purchase_price",
    "purchase_currency", "supplier", "notes",
]

PARTS_IMPORT_FIELDS = [
    "part_code", "name", "short_description", "part_kind",
    "manufacturer", "manufacturer_part_number", "default_unit",
    "package_type", "spec_summary", "tags", "is_consumable",
    "is_serialised", "is_hazardous", "status", "notes",
]

STOCK_IMPORT_FIELDS = [
    "part_code", "quantity", "unit", "status", "condition",
    "location_name", "container_name", "serial_number", "batch_code",
    "purchase_date", "purchase_price", "purchase_currency", "supplier", "notes",
]


# ---------------------------------------------------------------------------
# Parts export
# ---------------------------------------------------------------------------

@router.get(
    "/parts/export",
    summary="Export all parts as CSV",
    response_class=StreamingResponse,
)
async def export_parts_csv(
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    result = await db.execute(select(Part).order_by(Part.name))
    parts = result.scalars().all()

    rows = []
    for p in parts:
        tags_str = ",".join(p.tags) if p.tags else ""
        rows.append({
            "part_code": p.part_code,
            "name": p.name,
            "short_description": p.short_description or "",
            "part_kind": p.part_kind or "",
            "manufacturer": p.manufacturer or "",
            "manufacturer_part_number": p.manufacturer_part_number or "",
            "default_unit": p.default_unit,
            "package_type": p.package_type or "",
            "spec_summary": p.spec_summary or "",
            "tags": tags_str,
            "is_consumable": str(p.is_consumable).lower(),
            "is_serialised": str(p.is_serialised).lower(),
            "is_hazardous": str(p.is_hazardous).lower(),
            "status": p.status,
            "notes": p.notes or "",
        })

    return _csv_streaming_response(rows, "makervault_parts.csv")


@router.get(
    "/parts/template",
    summary="Download blank parts import CSV template",
    response_class=StreamingResponse,
)
async def parts_csv_template() -> StreamingResponse:
    return _empty_csv_response(PARTS_IMPORT_FIELDS, "parts_import_template.csv")


# ---------------------------------------------------------------------------
# Parts import
# ---------------------------------------------------------------------------

@router.post(
    "/parts/import",
    summary="Import parts from a CSV file",
    status_code=status.HTTP_200_OK,
)
async def import_parts_csv(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Import parts from a CSV file.

    Rows with an existing ``part_code`` are **skipped** (no overwrites).
    Returns a summary: ``created``, ``skipped``, and a list of ``errors``.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file must be a .csv file.",
        )

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # strip BOM if present
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV file must be UTF-8 encoded.",
        )

    reader = csv.DictReader(io.StringIO(text))
    required = {"part_code", "name"}
    if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV must contain at minimum these columns: {sorted(required)}",
        )

    created = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        part_code = (row.get("part_code") or "").strip()
        name = (row.get("name") or "").strip()

        if not part_code or not name:
            errors.append(f"Row {row_num}: part_code and name are required — skipped.")
            skipped += 1
            continue

        # Skip duplicates
        existing = (await db.execute(
            select(Part).where(Part.part_code == part_code)
        )).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue

        # Parse optional boolean columns
        def _bool(val: str | None) -> bool:
            return (val or "").strip().lower() in ("true", "1", "yes")

        # Parse tags (comma-separated string in the CSV)
        tags_raw = (row.get("tags") or "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else None

        # Validate status
        raw_status = (row.get("status") or "draft").strip()
        from makervault.models.part import PART_STATUS_VALUES
        if raw_status not in PART_STATUS_VALUES:
            raw_status = "draft"

        # Validate part_kind
        raw_kind = (row.get("part_kind") or "").strip() or None
        from makervault.models.part import PART_KIND_VALUES
        if raw_kind and raw_kind not in PART_KIND_VALUES:
            raw_kind = None

        try:
            part_data = PartCreate(
                part_code=part_code,
                name=name,
                short_description=(row.get("short_description") or "").strip() or None,
                part_kind=raw_kind,
                manufacturer=(row.get("manufacturer") or "").strip() or None,
                manufacturer_part_number=(row.get("manufacturer_part_number") or "").strip() or None,
                default_unit=(row.get("default_unit") or "pcs").strip(),
                package_type=(row.get("package_type") or "").strip() or None,
                spec_summary=(row.get("spec_summary") or "").strip() or None,
                tags=tags,
                is_consumable=_bool(row.get("is_consumable")),
                is_serialised=_bool(row.get("is_serialised")),
                is_hazardous=_bool(row.get("is_hazardous")),
                status=raw_status,
                notes=(row.get("notes") or "").strip() or None,
            )
        except Exception as exc:
            # Sanitise the exception message — expose only the first line to avoid
            # leaking internal stack information.
            first_line = str(exc).split("\n")[0][:200]
            errors.append(f"Row {row_num} ({part_code}): validation error — {first_line}")
            skipped += 1
            continue

        data = part_data.model_dump()
        try:
            if db.sync_session.get_bind().dialect.name != "postgresql":
                data.pop("aliases", None)
                data.pop("tags", None)
        except AttributeError:
            # Dialect introspection not available (e.g. async session wrapper);
            # leave the data as-is and let the ORM handle it.
            pass

        part = Part(**data)
        db.add(part)
        created += 1

    await db.flush()

    return {"created": created, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Stock export
# ---------------------------------------------------------------------------

@router.get(
    "/stock/export",
    summary="Export all stock items as CSV",
    response_class=StreamingResponse,
)
async def export_stock_csv(
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    result = await db.execute(
        select(StockItem).order_by(StockItem.created_at.desc())
    )
    items = result.scalars().all()

    # Build lookup maps
    part_ids = {item.part_id for item in items}
    location_ids = {item.location_id for item in items if item.location_id}
    container_ids = {item.container_id for item in items if item.container_id}

    parts_map: dict[str, Part] = {}
    if part_ids:
        parts_result = await db.execute(select(Part).where(Part.id.in_(part_ids)))
        parts_map = {str(p.id): p for p in parts_result.scalars().all()}

    location_names: dict[str, str] = {}
    if location_ids:
        locs = (await db.execute(select(Location).where(Location.id.in_(location_ids)))).scalars().all()
        location_names = {str(loc.id): loc.name for loc in locs}

    container_names: dict[str, str] = {}
    if container_ids:
        ctrs = (await db.execute(select(Container).where(Container.id.in_(container_ids)))).scalars().all()
        container_names = {str(ctr.id): ctr.name for ctr in ctrs}

    rows = []
    for item in items:
        part = parts_map.get(str(item.part_id))
        rows.append({
            "stock_item_id": str(item.id),
            "part_code": part.part_code if part else str(item.part_id),
            "part_name": part.name if part else "",
            "quantity": item.quantity,
            "unit": item.unit or "",
            "status": item.status,
            "condition": item.condition or "",
            "location_name": location_names.get(str(item.location_id), "") if item.location_id else "",
            "container_name": container_names.get(str(item.container_id), "") if item.container_id else "",
            "serial_number": item.serial_number or "",
            "batch_code": item.batch_code or "",
            "purchase_date": str(item.purchase_date) if item.purchase_date else "",
            "purchase_price": item.purchase_price if item.purchase_price is not None else "",
            "purchase_currency": item.purchase_currency or "",
            "supplier": item.supplier or "",
            "notes": item.notes or "",
        })

    return _csv_streaming_response(rows, "makervault_stock.csv")


@router.get(
    "/stock/template",
    summary="Download blank stock import CSV template",
    response_class=StreamingResponse,
)
async def stock_csv_template() -> StreamingResponse:
    return _empty_csv_response(STOCK_IMPORT_FIELDS, "stock_import_template.csv")


# ---------------------------------------------------------------------------
# Stock import
# ---------------------------------------------------------------------------

@router.post(
    "/stock/import",
    summary="Import stock items from a CSV file",
    status_code=status.HTTP_200_OK,
)
async def import_stock_csv(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Import stock items from a CSV file.

    Each row must reference a ``part_code`` that already exists in the
    catalogue.  A row must have exactly one of ``location_name`` or
    ``container_name`` (but not both, and not neither).

    Returns a summary: ``created``, ``skipped``, and a list of ``errors``.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file must be a .csv file.",
        )

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV file must be UTF-8 encoded.",
        )

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "part_code" not in reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV must contain at minimum a 'part_code' column.",
        )

    # Cache part lookups and placement lookups to avoid repeated queries
    part_cache: dict[str, Part | None] = {}
    location_cache: dict[str, Location | None] = {}
    container_cache: dict[str, Container | None] = {}

    async def _get_part(code: str) -> Part | None:
        if code not in part_cache:
            res = (await db.execute(select(Part).where(Part.part_code == code))).scalar_one_or_none()
            part_cache[code] = res
        return part_cache[code]

    async def _get_location(name: str) -> Location | None:
        if name not in location_cache:
            res = (await db.execute(select(Location).where(Location.name == name))).scalar_one_or_none()
            location_cache[name] = res
        return location_cache[name]

    async def _get_container(name: str) -> Container | None:
        if name not in container_cache:
            res = (await db.execute(select(Container).where(Container.name == name))).scalar_one_or_none()
            container_cache[name] = res
        return container_cache[name]

    created = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        part_code = (row.get("part_code") or "").strip()
        if not part_code:
            errors.append(f"Row {row_num}: part_code is required — skipped.")
            skipped += 1
            continue

        part = await _get_part(part_code)
        if part is None:
            errors.append(f"Row {row_num}: part_code '{part_code}' not found — skipped.")
            skipped += 1
            continue

        location_name = (row.get("location_name") or "").strip()
        container_name = (row.get("container_name") or "").strip()

        if location_name and container_name:
            errors.append(
                f"Row {row_num}: provide location_name OR container_name, not both — skipped."
            )
            skipped += 1
            continue
        if not location_name and not container_name:
            errors.append(
                f"Row {row_num}: one of location_name or container_name is required — skipped."
            )
            skipped += 1
            continue

        location_id: uuid.UUID | None = None
        container_id: uuid.UUID | None = None

        if location_name:
            loc = await _get_location(location_name)
            if loc is None:
                errors.append(f"Row {row_num}: location '{location_name}' not found — skipped.")
                skipped += 1
                continue
            location_id = loc.id

        if container_name:
            ctr = await _get_container(container_name)
            if ctr is None:
                errors.append(f"Row {row_num}: container '{container_name}' not found — skipped.")
                skipped += 1
                continue
            container_id = ctr.id

        # Parse numeric quantity
        try:
            quantity = float((row.get("quantity") or "1").strip())
            if quantity <= 0:
                raise ValueError("must be positive")
        except ValueError:
            errors.append(f"Row {row_num}: invalid quantity — skipped.")
            skipped += 1
            continue

        raw_status = (row.get("status") or "available").strip()
        if raw_status not in STOCK_STATUS_VALUES:
            raw_status = "available"

        raw_condition = (row.get("condition") or "").strip() or None
        if raw_condition and raw_condition not in STOCK_CONDITION_VALUES:
            raw_condition = None

        purchase_price: float | None = None
        raw_price = (row.get("purchase_price") or "").strip()
        if raw_price:
            try:
                purchase_price = float(raw_price)
            except ValueError:
                purchase_price = None

        from datetime import date
        purchase_date_val: date | None = None
        raw_date = (row.get("purchase_date") or "").strip()
        if raw_date:
            try:
                purchase_date_val = date.fromisoformat(raw_date)
            except ValueError:
                purchase_date_val = None

        try:
            item_data = StockItemCreate(
                part_id=part.id,
                location_id=location_id,
                container_id=container_id,
                quantity=quantity,
                unit=(row.get("unit") or "").strip() or None,
                status=raw_status,
                condition=raw_condition,
                serial_number=(row.get("serial_number") or "").strip() or None,
                batch_code=(row.get("batch_code") or "").strip() or None,
                purchase_date=purchase_date_val,
                purchase_price=purchase_price,
                purchase_currency=(row.get("purchase_currency") or "").strip() or None,
                supplier=(row.get("supplier") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
            )
        except Exception as exc:
            # Sanitise the exception message — expose only the first line to avoid
            # leaking internal stack information.
            first_line = str(exc).split("\n")[0][:200]
            errors.append(f"Row {row_num} ({part_code}): validation error — {first_line}")
            skipped += 1
            continue

        stock_item = StockItem(**item_data.model_dump())
        db.add(stock_item)
        created += 1

    await db.flush()

    return {"created": created, "skipped": skipped, "errors": errors}
