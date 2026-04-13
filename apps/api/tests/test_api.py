"""API endpoint tests for EPIC 4 — parts, stock, locations, containers, categories.

Uses a shared SQLite in-memory database with a simplified schema.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# Fixtures — SQLite schema + client with DB override
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def api_engine():
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_category_id TEXT REFERENCES categories(id),
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
                parent_location_id TEXT REFERENCES locations(id),
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
                location_id TEXT REFERENCES locations(id),
                parent_container_id TEXT REFERENCES containers(id),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN parent_container_id IS NOT NULL THEN 1 ELSE 0 END = 1
                )
            )
        """))
        await conn.execute(text("""
            CREATE TABLE parts (
                id TEXT PRIMARY KEY,
                part_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                short_description TEXT,
                long_description TEXT,
                category_id TEXT REFERENCES categories(id),
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
                part_id TEXT NOT NULL REFERENCES parts(id),
                location_id TEXT REFERENCES locations(id),
                container_id TEXT REFERENCES containers(id),
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
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN container_id IS NOT NULL THEN 1 ELSE 0 END = 1
                )
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def api_session(api_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=api_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def api_client(api_session: AsyncSession) -> AsyncClient:
    from httpx import ASGITransport

    async def _override_db():
        try:
            yield api_session
            await api_session.commit()
        except Exception:
            await api_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Category endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_category(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/categories", json={"name": "Sensors"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Sensors"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_categories(api_client: AsyncClient) -> None:
    await api_client.post("/api/categories", json={"name": "Cat A"})
    await api_client.post("/api/categories", json={"name": "Cat B"})
    r = await api_client.get("/api/categories")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_category(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/categories", json={"name": "Get Me"})
    cat_id = r.json()["id"]
    r2 = await api_client.get(f"/api/categories/{cat_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_category_404(api_client: AsyncClient) -> None:
    r = await api_client.get(f"/api/categories/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_category(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/categories", json={"name": "Old Name"})
    cat_id = r.json()["id"]
    r2 = await api_client.patch(f"/api/categories/{cat_id}", json={"name": "New Name"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_category(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/categories", json={"name": "Delete Me"})
    cat_id = r.json()["id"]
    r2 = await api_client.delete(f"/api/categories/{cat_id}")
    assert r2.status_code == 204
    r3 = await api_client.get(f"/api/categories/{cat_id}")
    assert r3.status_code == 404


# ---------------------------------------------------------------------------
# Location endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_location(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/locations", json={"name": "Garage"})
    assert r.status_code == 201
    assert r.json()["name"] == "Garage"


@pytest.mark.asyncio
async def test_list_locations(api_client: AsyncClient) -> None:
    await api_client.post("/api/locations", json={"name": "Room 1"})
    r = await api_client.get("/api/locations")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_location_not_found(api_client: AsyncClient) -> None:
    r = await api_client.get(f"/api/locations/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_location(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/locations", json={"name": "Old Loc"})
    loc_id = r.json()["id"]
    r2 = await api_client.patch(f"/api/locations/{loc_id}", json={"name": "New Loc"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "New Loc"


# ---------------------------------------------------------------------------
# Container endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_container_in_location(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/locations", json={"name": "Shelf"})
    loc_id = r.json()["id"]
    r2 = await api_client.post(
        "/api/containers", json={"name": "Box A", "location_id": loc_id}
    )
    assert r2.status_code == 201
    data = r2.json()
    assert data["name"] == "Box A"
    assert data["location_id"] == loc_id


@pytest.mark.asyncio
async def test_container_requires_parent(api_client: AsyncClient) -> None:
    r = await api_client.post("/api/containers", json={"name": "Orphan"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_container_not_found(api_client: AsyncClient) -> None:
    r = await api_client.get(f"/api/containers/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_nested_container(api_client: AsyncClient) -> None:
    r_loc = await api_client.post("/api/locations", json={"name": "Lab"})
    loc_id = r_loc.json()["id"]
    r_outer = await api_client.post(
        "/api/containers", json={"name": "Case", "location_id": loc_id}
    )
    outer_id = r_outer.json()["id"]
    r_inner = await api_client.post(
        "/api/containers", json={"name": "Tray", "parent_container_id": outer_id}
    )
    assert r_inner.status_code == 201
    assert r_inner.json()["parent_container_id"] == outer_id


# ---------------------------------------------------------------------------
# Part endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_part(api_client: AsyncClient) -> None:
    r = await api_client.post(
        "/api/parts", json={"part_code": "ESP32-001", "name": "ESP32 DevKit"}
    )
    assert r.status_code == 201
    assert r.json()["part_code"] == "ESP32-001"


@pytest.mark.asyncio
async def test_part_code_conflict(api_client: AsyncClient) -> None:
    body = {"part_code": "DUPE-CODE", "name": "Part"}
    await api_client.post("/api/parts", json=body)
    r = await api_client.post("/api/parts", json=body)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_parts(api_client: AsyncClient) -> None:
    await api_client.post("/api/parts", json={"part_code": "P-LIST-1", "name": "Part 1"})
    r = await api_client.get("/api/parts")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_search_parts(api_client: AsyncClient) -> None:
    await api_client.post(
        "/api/parts",
        json={"part_code": "SEARCH-001", "name": "Raspberry Pi Zero"},
    )
    r = await api_client.get("/api/parts?q=Raspberry")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()["items"]]
    assert any("Raspberry" in n for n in names)


@pytest.mark.asyncio
async def test_search_parts_no_results(api_client: AsyncClient) -> None:
    r = await api_client.get("/api/parts?q=ZZZNOMATCH99999")
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_part_not_found(api_client: AsyncClient) -> None:
    r = await api_client.get(f"/api/parts/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_part(api_client: AsyncClient) -> None:
    r = await api_client.post(
        "/api/parts", json={"part_code": "UPDATE-001", "name": "Original"}
    )
    part_id = r.json()["id"]
    r2 = await api_client.patch(f"/api/parts/{part_id}", json={"name": "Updated"})
    assert r2.status_code == 200
    assert r2.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_part(api_client: AsyncClient) -> None:
    r = await api_client.post(
        "/api/parts", json={"part_code": "DEL-001", "name": "Delete Me"}
    )
    part_id = r.json()["id"]
    r2 = await api_client.delete(f"/api/parts/{part_id}")
    assert r2.status_code == 204
    r3 = await api_client.get(f"/api/parts/{part_id}")
    assert r3.status_code == 404


# ---------------------------------------------------------------------------
# Stock item endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def stock_setup(api_client: AsyncClient):
    """Create a location, container, and part for stock tests."""
    loc_r = await api_client.post("/api/locations", json={"name": "Stock Shelf"})
    loc_id = loc_r.json()["id"]
    container_r = await api_client.post(
        "/api/containers", json={"name": "Stock Bin", "location_id": loc_id}
    )
    container_id = container_r.json()["id"]
    part_r = await api_client.post(
        "/api/parts", json={"part_code": "STOCK-PART-001", "name": "Stock Part"}
    )
    part_id = part_r.json()["id"]
    return {"loc_id": loc_id, "container_id": container_id, "part_id": part_id}


@pytest.mark.asyncio
async def test_create_stock_item_in_container(
    api_client: AsyncClient, stock_setup
) -> None:
    r = await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "container_id": stock_setup["container_id"],
            "quantity": 10,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["quantity"] == 10.0
    assert data["container_id"] == stock_setup["container_id"]


@pytest.mark.asyncio
async def test_create_stock_item_in_location(
    api_client: AsyncClient, stock_setup
) -> None:
    r = await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "quantity": 5,
        },
    )
    assert r.status_code == 201
    assert r.json()["location_id"] == stock_setup["loc_id"]


@pytest.mark.asyncio
async def test_stock_item_dual_placement_rejected(
    api_client: AsyncClient, stock_setup
) -> None:
    r = await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "container_id": stock_setup["container_id"],
            "quantity": 1,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stock_item_no_placement_rejected(
    api_client: AsyncClient, stock_setup
) -> None:
    r = await api_client.post(
        "/api/stock",
        json={"part_id": stock_setup["part_id"], "quantity": 1},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_stock(api_client: AsyncClient, stock_setup) -> None:
    await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "quantity": 3,
        },
    )
    r = await api_client.get("/api/stock")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_filter_stock_by_part(api_client: AsyncClient, stock_setup) -> None:
    await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "quantity": 7,
        },
    )
    r = await api_client.get(f"/api/stock?part_id={stock_setup['part_id']}")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["part_id"] == stock_setup["part_id"]


@pytest.mark.asyncio
async def test_update_stock_item(api_client: AsyncClient, stock_setup) -> None:
    r = await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "quantity": 10,
        },
    )
    item_id = r.json()["id"]
    r2 = await api_client.patch(f"/api/stock/{item_id}", json={"quantity": 3})
    assert r2.status_code == 200
    assert r2.json()["quantity"] == 3.0


@pytest.mark.asyncio
async def test_delete_stock_item(api_client: AsyncClient, stock_setup) -> None:
    r = await api_client.post(
        "/api/stock",
        json={
            "part_id": stock_setup["part_id"],
            "location_id": stock_setup["loc_id"],
            "quantity": 1,
        },
    )
    item_id = r.json()["id"]
    r2 = await api_client.delete(f"/api/stock/{item_id}")
    assert r2.status_code == 204
    r3 = await api_client.get(f"/api/stock/{item_id}")
    assert r3.status_code == 404


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pagination(api_client: AsyncClient) -> None:
    for i in range(5):
        await api_client.post("/api/categories", json={"name": f"Pag Cat {i}"})
    r = await api_client.get("/api/categories?limit=2&skip=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 5
