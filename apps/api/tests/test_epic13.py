"""Tests for Epic 13 — Imports, labels, and operational polish.

Covers:
- GET  /api/import-export/parts/template          — blank CSV download
- GET  /api/import-export/stock/template          — blank CSV download
- GET  /api/import-export/parts/export            — exports all parts
- GET  /api/import-export/stock/export            — exports all stock
- POST /api/import-export/parts/import            — import new parts
- POST /api/import-export/parts/import duplicate  — existing part_code skipped
- POST /api/import-export/parts/import no_file    — non-CSV rejected (422)
- POST /api/import-export/parts/import missing_col — CSV without name col → 422
- POST /api/import-export/stock/import            — import stock items
- POST /api/import-export/stock/import bad_ref    — unknown part_code → skipped
- POST /api/import-export/stock/import no_placement — missing placement → skipped
- POST /api/import-export/stock/import both_placements — both placements → skipped
- POST /api/stock/bulk-move                       — move multiple items
- POST /api/stock/bulk-move bad_destination       — unknown location → 404
- POST /api/stock/bulk-move missing destination   — no dest → 422
- POST /api/stock/bulk-move partial               — some IDs not found reported
- GET  /api/parts/duplicates                      — returns duplicate groups
- GET  /api/parts/duplicates none                 — empty when no dups
- API version reflects 1.0.0
"""

import io
import csv
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def e13_engine():
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_category_id TEXT,
                description TEXT,
                sort_order INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE locations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                parent_location_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE containers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                label_code TEXT UNIQUE,
                location_id TEXT,
                parent_container_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE parts (
                id TEXT PRIMARY KEY,
                part_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                short_description TEXT,
                long_description TEXT,
                category_id TEXT,
                part_kind TEXT,
                manufacturer TEXT,
                manufacturer_part_number TEXT,
                default_unit TEXT NOT NULL DEFAULT 'pcs',
                package_type TEXT,
                spec_summary TEXT,
                capabilities_json TEXT,
                tags TEXT,
                aliases TEXT,
                search_text TEXT,
                is_consumable INTEGER NOT NULL DEFAULT 0,
                is_serialised INTEGER NOT NULL DEFAULT 0,
                is_hazardous INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'draft',
                identification_confidence INTEGER,
                needs_review INTEGER NOT NULL DEFAULT 0,
                provenance TEXT DEFAULT 'manual',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE stock_items (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL,
                location_id TEXT,
                container_id TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                condition TEXT,
                serial_number TEXT,
                batch_code TEXT,
                purchase_date TEXT,
                purchase_price REAL,
                purchase_currency TEXT,
                supplier TEXT,
                notes TEXT,
                last_seen_at TIMESTAMP,
                is_reserved INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE project_parts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                part_id TEXT NOT NULL,
                quantity_required REAL NOT NULL DEFAULT 1,
                unit TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE usage_history (
                id TEXT PRIMARY KEY,
                stock_item_id TEXT,
                project_id TEXT,
                part_id TEXT,
                action_type TEXT NOT NULL,
                quantity_delta REAL,
                used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def e13_session(e13_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e13_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e13_client(e13_session: AsyncSession) -> AsyncClient:
    async def _override_db():
        try:
            yield e13_session
            await e13_session.commit()
        except Exception:
            await e13_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csv_bytes(rows: list[dict], fieldnames: list[str] | None = None) -> bytes:
    buf = io.StringIO()
    fn = fieldnames or (list(rows[0].keys()) if rows else [])
    writer = csv.DictWriter(buf, fieldnames=fn)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


async def _create_part(client: AsyncClient, part_code: str, name: str) -> dict:
    resp = await client.post("/api/parts", json={"part_code": part_code, "name": name})
    assert resp.status_code == 201
    return resp.json()


async def _create_location(client: AsyncClient, name: str) -> dict:
    resp = await client.post("/api/locations", json={"name": name})
    assert resp.status_code == 201
    return resp.json()


async def _create_container(client: AsyncClient, name: str, location_id: str) -> dict:
    resp = await client.post("/api/containers", json={"name": name, "location_id": location_id})
    assert resp.status_code == 201
    return resp.json()


async def _create_stock(client: AsyncClient, part_id: str, location_id: str, qty: float = 5) -> dict:
    resp = await client.post("/api/stock", json={
        "part_id": part_id,
        "location_id": location_id,
        "quantity": qty,
    })
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Template downloads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parts_template_download(e13_client: AsyncClient):
    resp = await e13_client.get("/api/import-export/parts/template")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames is not None
    assert "part_code" in reader.fieldnames
    assert "name" in reader.fieldnames
    # Template has header only — no data rows
    rows = list(reader)
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_stock_template_download(e13_client: AsyncClient):
    resp = await e13_client.get("/api/import-export/stock/template")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    reader = csv.DictReader(io.StringIO(resp.text))
    assert reader.fieldnames is not None
    assert "part_code" in reader.fieldnames


# ---------------------------------------------------------------------------
# Parts export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parts_export_empty(e13_client: AsyncClient):
    resp = await e13_client.get("/api/import-export/parts/export")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_parts_export_with_data(e13_client: AsyncClient):
    await _create_part(e13_client, "RES-001", "10k Resistor")
    await _create_part(e13_client, "CAP-001", "100nF Capacitor")
    resp = await e13_client.get("/api/import-export/parts/export")
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2
    codes = {r["part_code"] for r in rows}
    assert codes == {"RES-001", "CAP-001"}


# ---------------------------------------------------------------------------
# Stock export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stock_export_with_data(e13_client: AsyncClient):
    part = await _create_part(e13_client, "LED-001", "Red LED")
    loc = await _create_location(e13_client, "Shelf A")
    await _create_stock(e13_client, part["id"], loc["id"], qty=20)
    resp = await e13_client.get("/api/import-export/stock/export")
    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["part_code"] == "LED-001"
    assert float(rows[0]["quantity"]) == 20.0


# ---------------------------------------------------------------------------
# Parts import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parts_import_creates_parts(e13_client: AsyncClient):
    csv_data = _csv_bytes([
        {"part_code": "IC-001", "name": "NE555 Timer"},
        {"part_code": "IC-002", "name": "LM358 Op-Amp"},
    ])
    resp = await e13_client.post(
        "/api/import-export/parts/import",
        files={"file": ("parts.csv", csv_data, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []

    # Verify parts exist
    list_resp = await e13_client.get("/api/parts")
    assert list_resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_parts_import_skips_existing_part_code(e13_client: AsyncClient):
    await _create_part(e13_client, "IC-DUP", "Original Part")
    csv_data = _csv_bytes([
        {"part_code": "IC-DUP", "name": "Duplicate Part"},
        {"part_code": "IC-NEW", "name": "New Part"},
    ])
    resp = await e13_client.post(
        "/api/import-export/parts/import",
        files={"file": ("parts.csv", csv_data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_parts_import_rejects_non_csv(e13_client: AsyncClient):
    resp = await e13_client.post(
        "/api/import-export/parts/import",
        files={"file": ("parts.txt", b"not a csv", "text/plain")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parts_import_missing_required_column(e13_client: AsyncClient):
    """CSV missing the 'name' column is rejected outright."""
    csv_data = _csv_bytes([{"part_code": "X-001", "short_description": "No name"}],
                          fieldnames=["part_code", "short_description"])
    resp = await e13_client.post(
        "/api/import-export/parts/import",
        files={"file": ("parts.csv", csv_data, "text/csv")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_parts_import_row_missing_name_skipped(e13_client: AsyncClient):
    """A row with an empty name is skipped, not a fatal error."""
    csv_data = _csv_bytes([
        {"part_code": "GOOD-001", "name": "Good Part"},
        {"part_code": "BAD-001", "name": ""},
    ])
    resp = await e13_client.post(
        "/api/import-export/parts/import",
        files={"file": ("parts.csv", csv_data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped"] == 1
    assert len(body["errors"]) == 1


# ---------------------------------------------------------------------------
# Stock import
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stock_import_creates_items(e13_client: AsyncClient):
    await _create_part(e13_client, "CAP-100", "100nF Cap")
    await _create_location(e13_client, "Bin 1")
    csv_data = _csv_bytes([
        {"part_code": "CAP-100", "quantity": "50", "location_name": "Bin 1", "container_name": ""},
    ])
    resp = await e13_client.post(
        "/api/import-export/stock/import",
        files={"file": ("stock.csv", csv_data, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped"] == 0

    list_resp = await e13_client.get("/api/stock")
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["quantity"] == 50.0


@pytest.mark.asyncio
async def test_stock_import_unknown_part_code_skipped(e13_client: AsyncClient):
    await _create_location(e13_client, "Shelf X")
    csv_data = _csv_bytes([
        {"part_code": "NO-EXIST", "quantity": "10", "location_name": "Shelf X", "container_name": ""},
    ])
    resp = await e13_client.post(
        "/api/import-export/stock/import",
        files={"file": ("stock.csv", csv_data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["skipped"] == 1
    assert "NO-EXIST" in body["errors"][0]


@pytest.mark.asyncio
async def test_stock_import_no_placement_skipped(e13_client: AsyncClient):
    await _create_part(e13_client, "RES-NP", "No Placement Part")
    csv_data = _csv_bytes([
        {"part_code": "RES-NP", "quantity": "5", "location_name": "", "container_name": ""},
    ])
    resp = await e13_client.post(
        "/api/import-export/stock/import",
        files={"file": ("stock.csv", csv_data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_stock_import_both_placements_skipped(e13_client: AsyncClient):
    await _create_part(e13_client, "RES-BP", "Both Placement Part")
    await _create_location(e13_client, "Loc Both")
    loc_resp = await e13_client.get("/api/locations")
    csv_data = _csv_bytes([
        {"part_code": "RES-BP", "quantity": "5",
         "location_name": "Loc Both", "container_name": "SomeContainer"},
    ])
    resp = await e13_client.post(
        "/api/import-export/stock/import",
        files={"file": ("stock.csv", csv_data, "text/csv")},
    )
    body = resp.json()
    assert body["created"] == 0
    assert body["skipped"] == 1


# ---------------------------------------------------------------------------
# Bulk move
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bulk_move_stock_to_location(e13_client: AsyncClient):
    part = await _create_part(e13_client, "BM-PART", "Bulk Move Part")
    loc1 = await _create_location(e13_client, "Source Loc")
    loc2 = await _create_location(e13_client, "Dest Loc")
    s1 = await _create_stock(e13_client, part["id"], loc1["id"])
    s2 = await _create_stock(e13_client, part["id"], loc1["id"])

    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [s1["id"], s2["id"]],
        "location_id": loc2["id"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["moved"] == 2
    assert body["not_found"] == []

    # Verify relocation
    s1_updated = (await e13_client.get(f"/api/stock/{s1['id']}")).json()
    assert s1_updated["location_id"] == loc2["id"]


@pytest.mark.asyncio
async def test_bulk_move_to_container(e13_client: AsyncClient):
    part = await _create_part(e13_client, "BM-PART2", "Bulk Move Part 2")
    loc = await _create_location(e13_client, "Container Loc")
    ctr = await _create_container(e13_client, "Tray A", loc["id"])
    s1 = await _create_stock(e13_client, part["id"], loc["id"])

    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [s1["id"]],
        "container_id": ctr["id"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["moved"] == 1


@pytest.mark.asyncio
async def test_bulk_move_unknown_destination_404(e13_client: AsyncClient):
    part = await _create_part(e13_client, "BM-404", "404 Part")
    loc = await _create_location(e13_client, "Loc 404")
    s1 = await _create_stock(e13_client, part["id"], loc["id"])
    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [s1["id"]],
        "location_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_bulk_move_missing_destination_422(e13_client: AsyncClient):
    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [str(uuid.uuid4())],
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_move_both_destinations_422(e13_client: AsyncClient):
    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [str(uuid.uuid4())],
        "location_id": str(uuid.uuid4()),
        "container_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bulk_move_partial_not_found_reported(e13_client: AsyncClient):
    part = await _create_part(e13_client, "BM-PARTIAL", "Partial Part")
    loc1 = await _create_location(e13_client, "Partial Src")
    loc2 = await _create_location(e13_client, "Partial Dst")
    s1 = await _create_stock(e13_client, part["id"], loc1["id"])
    missing_id = str(uuid.uuid4())

    resp = await e13_client.post("/api/stock/bulk-move", json={
        "stock_item_ids": [s1["id"], missing_id],
        "location_id": loc2["id"],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["moved"] == 1
    assert missing_id in body["not_found"]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicates_empty_when_no_parts(e13_client: AsyncClient):
    resp = await e13_client.get("/api/parts/duplicates")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_duplicates_finds_same_name(e13_client: AsyncClient):
    await _create_part(e13_client, "DUP-A", "Arduino Uno")
    await _create_part(e13_client, "DUP-B", "Arduino Uno")  # same name
    await _create_part(e13_client, "UNIQUE-1", "Raspberry Pi")  # unique

    resp = await e13_client.get("/api/parts/duplicates")
    assert resp.status_code == 200
    groups = resp.json()
    assert len(groups) == 1
    assert groups[0]["reason"] == "same_name"
    codes = {p["part_code"] for p in groups[0]["parts"]}
    assert codes == {"DUP-A", "DUP-B"}


@pytest.mark.asyncio
async def test_duplicates_no_false_positives_for_unique_parts(e13_client: AsyncClient):
    await _create_part(e13_client, "U1", "Unique Part Alpha")
    await _create_part(e13_client, "U2", "Unique Part Beta")
    await _create_part(e13_client, "U3", "Unique Part Gamma")
    resp = await e13_client.get("/api/parts/duplicates")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Version check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_version_is_1_0_0(e13_client: AsyncClient):
    resp = await e13_client.get("/api/openapi.json")
    assert resp.status_code == 200
    info = resp.json().get("info", {})
    assert info.get("version") == "1.0.0"
