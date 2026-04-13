"""Tests for Epic 12 — Usage history and stock lifecycle.

Covers:
- UsageHistory CRUD via /api/usage
- Create event with valid action_type
- Create event with invalid action_type → 422
- Create event linked to non-existent StockItem → 404
- Create event linked to non-existent Project → 404
- Create event linked to non-existent Part → 404
- quantity_delta applied to StockItem.quantity on create
- Quantity cannot go below zero
- part_id auto-populated from stock_item.part_id when not provided
- used_at defaults to now when not provided
- List events filtered by stock_item_id
- List events filtered by project_id
- List events filtered by part_id
- List events filtered by action_type
- Get event by ID
- Get non-existent event → 404
- Delete event
- Delete non-existent event → 404
- Pagination: skip and limit
- Project-linked usage recording
- Audit history: multiple events for the same stock item
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (Epic-12-specific schema)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def e12_engine():
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
async def e12_session(e12_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e12_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e12_client(e12_session: AsyncSession) -> AsyncClient:
    async def _override_db():
        try:
            yield e12_session
            await e12_session.commit()
        except Exception:
            await e12_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_part(client: AsyncClient, **kwargs) -> str:
    payload = {"part_code": f"E12-{uuid.uuid4().hex[:6]}", "name": "Test Part", "status": "draft"}
    payload.update(kwargs)
    r = await client.post("/api/parts", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_location(client: AsyncClient) -> str:
    r = await client.post("/api/locations", json={"name": f"Shelf-{uuid.uuid4().hex[:4]}"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_stock(client: AsyncClient, part_id: str, location_id: str, qty: float = 10.0) -> str:
    r = await client.post(
        "/api/stock",
        json={"part_id": part_id, "location_id": location_id, "quantity": qty, "status": "available"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_project(client: AsyncClient, **kwargs) -> str:
    payload = {"name": f"Proj-{uuid.uuid4().hex[:4]}", "status": "active"}
    payload.update(kwargs)
    r = await client.post("/api/projects", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Tests — basic CRUD
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_usage_event_minimal(e12_client: AsyncClient):
    """Create a usage event with just action_type (no stock_item_id)."""
    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "used", "notes": "standalone test"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["action_type"] == "used"
    assert data["notes"] == "standalone test"
    assert data["stock_item_id"] is None
    assert data["project_id"] is None
    assert data["quantity_delta"] is None
    assert "used_at" in data
    assert "id" in data


@pytest.mark.anyio
async def test_create_usage_event_all_action_types(e12_client: AsyncClient):
    """All valid action_type values are accepted."""
    for action in ("allocated", "used", "returned", "consumed", "tested", "damaged"):
        r = await e12_client.post("/api/usage", json={"action_type": action})
        assert r.status_code == 201, f"{action}: {r.text}"
        assert r.json()["action_type"] == action


@pytest.mark.anyio
async def test_create_usage_event_invalid_action_type(e12_client: AsyncClient):
    """Invalid action_type is rejected with 422."""
    r = await e12_client.post("/api/usage", json={"action_type": "broken"})
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_usage_event_with_stock_item(e12_client: AsyncClient):
    """Create an event linked to a real StockItem."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=5.0)

    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "used", "stock_item_id": stock_id, "notes": "Used in lab"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["stock_item_id"] == stock_id
    assert data["part_id"] == part_id  # auto-populated


@pytest.mark.anyio
async def test_create_usage_event_missing_stock_item(e12_client: AsyncClient):
    """Event referencing a non-existent StockItem → 404."""
    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "used", "stock_item_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_create_usage_event_missing_project(e12_client: AsyncClient):
    """Event referencing a non-existent Project → 404."""
    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "allocated", "project_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_create_usage_event_missing_part(e12_client: AsyncClient):
    """Event referencing a non-existent Part → 404."""
    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "used", "part_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_usage_event(e12_client: AsyncClient):
    """Get a single usage event by ID."""
    r = await e12_client.post("/api/usage", json={"action_type": "tested", "notes": "bench test"})
    assert r.status_code == 201
    event_id = r.json()["id"]

    r2 = await e12_client.get(f"/api/usage/{event_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == event_id
    assert r2.json()["action_type"] == "tested"


@pytest.mark.anyio
async def test_get_usage_event_not_found(e12_client: AsyncClient):
    """Fetching a non-existent event returns 404."""
    r = await e12_client.get(f"/api/usage/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_delete_usage_event(e12_client: AsyncClient):
    """Delete a usage event."""
    r = await e12_client.post("/api/usage", json={"action_type": "damaged"})
    assert r.status_code == 201
    event_id = r.json()["id"]

    r2 = await e12_client.delete(f"/api/usage/{event_id}")
    assert r2.status_code == 204

    r3 = await e12_client.get(f"/api/usage/{event_id}")
    assert r3.status_code == 404


@pytest.mark.anyio
async def test_delete_usage_event_not_found(e12_client: AsyncClient):
    """Deleting a non-existent event returns 404."""
    r = await e12_client.delete(f"/api/usage/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tests — quantity_delta applies to StockItem
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_quantity_delta_decrements_stock(e12_client: AsyncClient):
    """Consuming stock (negative delta) reduces the StockItem quantity."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=10.0)

    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "consumed", "stock_item_id": stock_id, "quantity_delta": -3.0},
    )
    assert r.status_code == 201, r.text
    assert r.json()["quantity_delta"] == -3.0

    # Check stock item quantity updated
    sr = await e12_client.get(f"/api/stock/{stock_id}")
    assert sr.status_code == 200
    assert sr.json()["quantity"] == pytest.approx(7.0)


@pytest.mark.anyio
async def test_quantity_delta_increments_stock(e12_client: AsyncClient):
    """Returning stock (positive delta) increases the StockItem quantity."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=2.0)

    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "returned", "stock_item_id": stock_id, "quantity_delta": 5.0},
    )
    assert r.status_code == 201

    sr = await e12_client.get(f"/api/stock/{stock_id}")
    assert sr.json()["quantity"] == pytest.approx(7.0)


@pytest.mark.anyio
async def test_quantity_does_not_go_below_zero(e12_client: AsyncClient):
    """Consuming more than available clamps quantity at zero."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=2.0)

    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "consumed", "stock_item_id": stock_id, "quantity_delta": -100.0},
    )
    assert r.status_code == 201

    sr = await e12_client.get(f"/api/stock/{stock_id}")
    assert sr.json()["quantity"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests — filtering
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_filter_by_stock_item_id(e12_client: AsyncClient):
    """Filter events by stock_item_id."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id)

    # Event for our stock item
    await e12_client.post("/api/usage", json={"action_type": "used", "stock_item_id": stock_id})
    # Unrelated event
    await e12_client.post("/api/usage", json={"action_type": "tested"})

    r = await e12_client.get("/api/usage", params={"stock_item_id": stock_id})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["stock_item_id"] == stock_id


@pytest.mark.anyio
async def test_list_filter_by_project_id(e12_client: AsyncClient):
    """Filter events by project_id."""
    project_id = await _seed_project(e12_client)

    await e12_client.post("/api/usage", json={"action_type": "allocated", "project_id": project_id})
    await e12_client.post("/api/usage", json={"action_type": "used"})

    r = await e12_client.get("/api/usage", params={"project_id": project_id})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["project_id"] == project_id


@pytest.mark.anyio
async def test_list_filter_by_action_type(e12_client: AsyncClient):
    """Filter events by action_type."""
    await e12_client.post("/api/usage", json={"action_type": "consumed"})
    await e12_client.post("/api/usage", json={"action_type": "returned"})
    await e12_client.post("/api/usage", json={"action_type": "consumed"})

    r = await e12_client.get("/api/usage", params={"action_type": "consumed"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert all(item["action_type"] == "consumed" for item in data["items"])


@pytest.mark.anyio
async def test_list_filter_by_part_id(e12_client: AsyncClient):
    """Filter events by part_id."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id)

    # Event with explicit part_id
    await e12_client.post("/api/usage", json={"action_type": "used", "part_id": part_id})
    # Event with no part_id
    await e12_client.post("/api/usage", json={"action_type": "tested"})

    r = await e12_client.get("/api/usage", params={"part_id": part_id})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert all(item["part_id"] == part_id for item in data["items"])


# ---------------------------------------------------------------------------
# Tests — pagination
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_pagination(e12_client: AsyncClient):
    """skip and limit work correctly."""
    for _ in range(5):
        await e12_client.post("/api/usage", json={"action_type": "used"})

    r = await e12_client.get("/api/usage", params={"limit": 2, "skip": 0})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    assert r.json()["total"] >= 5

    r2 = await e12_client.get("/api/usage", params={"limit": 2, "skip": 2})
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 2


# ---------------------------------------------------------------------------
# Tests — project-linked usage
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_project_linked_usage(e12_client: AsyncClient):
    """Usage event can be linked to both a project and a stock item."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=8.0)
    project_id = await _seed_project(e12_client, name="LED Matrix Clock")

    r = await e12_client.post(
        "/api/usage",
        json={
            "action_type": "allocated",
            "stock_item_id": stock_id,
            "project_id": project_id,
            "quantity_delta": -2.0,
            "notes": "Reserved 2 units for LED matrix clock build",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["stock_item_id"] == stock_id
    assert data["project_id"] == project_id
    assert data["quantity_delta"] == -2.0

    # Verify by filtering on both dimensions
    r2 = await e12_client.get("/api/usage", params={"project_id": project_id})
    assert r2.json()["total"] == 1

    r3 = await e12_client.get("/api/usage", params={"stock_item_id": stock_id})
    assert r3.json()["total"] == 1


# ---------------------------------------------------------------------------
# Tests — audit history for a stock item
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_audit_history_multiple_events(e12_client: AsyncClient):
    """Multiple events for the same stock item are all retrievable."""
    part_id = await _seed_part(e12_client)
    loc_id = await _seed_location(e12_client)
    stock_id = await _seed_stock(e12_client, part_id, loc_id, qty=20.0)

    events = [
        ("allocated", -5.0),
        ("used", -2.0),
        ("returned", 1.0),
        ("tested", None),
        ("damaged", -1.0),
    ]
    for action, delta in events:
        payload: dict = {"action_type": action, "stock_item_id": stock_id}
        if delta is not None:
            payload["quantity_delta"] = delta
        r = await e12_client.post("/api/usage", json=payload)
        assert r.status_code == 201, f"{action}: {r.text}"

    r = await e12_client.get("/api/usage", params={"stock_item_id": stock_id, "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["items"]) == 5


@pytest.mark.anyio
async def test_used_at_defaults_to_now(e12_client: AsyncClient):
    """used_at is populated automatically when not supplied."""
    r = await e12_client.post("/api/usage", json={"action_type": "tested"})
    assert r.status_code == 201
    assert r.json()["used_at"] is not None


@pytest.mark.anyio
async def test_used_at_can_be_supplied(e12_client: AsyncClient):
    """used_at can be set explicitly for backdated events."""
    r = await e12_client.post(
        "/api/usage",
        json={"action_type": "used", "used_at": "2024-01-15T10:30:00Z"},
    )
    assert r.status_code == 201
    assert "2024-01-15" in r.json()["used_at"]
