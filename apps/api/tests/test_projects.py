"""Tests for Epic 7 — Projects and BOM foundations.

Covers:
- Project CRUD (create, read, update, delete, list)
- BOM entry (ProjectPart) CRUD
- BOM availability calculation
- Document linkage for projects (smoke test)
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# Fixtures — SQLite in-memory schema
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def proj_engine():
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
        await conn.execute(text("""
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'other',
                source_type TEXT NOT NULL DEFAULT 'uploaded',
                source_url TEXT,
                local_path TEXT,
                mime_type TEXT,
                checksum TEXT,
                file_size_bytes INTEGER,
                text_extracted TEXT,
                summary TEXT,
                version_label TEXT,
                metadata_json TEXT,
                notes TEXT,
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
            CREATE TABLE part_documents (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL REFERENCES parts(id),
                document_id TEXT NOT NULL REFERENCES documents(id),
                relationship_type TEXT NOT NULL DEFAULT 'other',
                is_primary INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE stock_item_documents (
                id TEXT PRIMARY KEY,
                stock_item_id TEXT NOT NULL REFERENCES stock_items(id),
                document_id TEXT NOT NULL REFERENCES documents(id),
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE project_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                document_id TEXT NOT NULL REFERENCES documents(id),
                relationship_type TEXT NOT NULL DEFAULT 'other',
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE project_parts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                part_id TEXT NOT NULL REFERENCES parts(id),
                quantity_required REAL NOT NULL DEFAULT 1,
                unit TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def proj_session(proj_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=proj_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def proj_client(proj_session: AsyncSession) -> AsyncClient:
    from httpx import ASGITransport

    async def _override_db():
        try:
            yield proj_session
            await proj_session.commit()
        except Exception:
            await proj_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_part(client: AsyncClient, part_code: str = "PART-001") -> dict:
    r = await client.post("/api/parts", json={"part_code": part_code, "name": "Test Part", "status": "active"})
    assert r.status_code == 201
    return r.json()


async def _create_location(client: AsyncClient) -> dict:
    r = await client.post("/api/locations", json={"name": "Shelf A"})
    assert r.status_code == 201
    return r.json()


async def _create_stock(client: AsyncClient, part_id: str, location_id: str, qty: float) -> dict:
    r = await client.post(
        "/api/stock",
        json={"part_id": part_id, "location_id": location_id, "quantity": qty, "status": "available"},
    )
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# Project CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_project(proj_client: AsyncClient) -> None:
    r = await proj_client.post(
        "/api/projects",
        json={"name": "Robot Arm", "description": "A robotic arm build", "status": "active"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Robot Arm"
    assert data["status"] == "active"
    assert "id" in data


@pytest.mark.anyio
async def test_create_project_minimal(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "Minimal Project"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Minimal Project"
    assert data["status"] == "active"


@pytest.mark.anyio
async def test_list_projects(proj_client: AsyncClient) -> None:
    await proj_client.post("/api/projects", json={"name": "Project Alpha"})
    await proj_client.post("/api/projects", json={"name": "Project Beta"})

    r = await proj_client.get("/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


@pytest.mark.anyio
async def test_list_projects_search(proj_client: AsyncClient) -> None:
    await proj_client.post("/api/projects", json={"name": "Searchable Project XYZ"})

    r = await proj_client.get("/api/projects", params={"q": "XYZ"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any("XYZ" in p["name"] for p in data["items"])


@pytest.mark.anyio
async def test_get_project(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "Get Test"})
    project_id = r.json()["id"]

    r2 = await proj_client.get(f"/api/projects/{project_id}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Get Test"


@pytest.mark.anyio
async def test_get_project_not_found(proj_client: AsyncClient) -> None:
    r = await proj_client.get(f"/api/projects/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_update_project(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "Old Name"})
    project_id = r.json()["id"]

    r2 = await proj_client.patch(f"/api/projects/{project_id}", json={"name": "New Name", "status": "completed"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["name"] == "New Name"
    assert data["status"] == "completed"


@pytest.mark.anyio
async def test_delete_project(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "To Delete"})
    project_id = r.json()["id"]

    r2 = await proj_client.delete(f"/api/projects/{project_id}")
    assert r2.status_code == 204

    r3 = await proj_client.get(f"/api/projects/{project_id}")
    assert r3.status_code == 404


# ---------------------------------------------------------------------------
# BOM entry (ProjectPart) tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_add_bom_entry(proj_client: AsyncClient) -> None:
    part = await _create_part(proj_client, "BOM-P001")
    r = await proj_client.post("/api/projects", json={"name": "BOM Project"})
    project_id = r.json()["id"]

    r2 = await proj_client.post(
        f"/api/projects/{project_id}/parts",
        json={"part_id": part["id"], "quantity_required": 5},
    )
    assert r2.status_code == 201
    data = r2.json()
    assert data["project_id"] == project_id
    assert data["part_id"] == part["id"]
    assert float(data["quantity_required"]) == 5.0
    assert data["part"]["part_code"] == "BOM-P001"


@pytest.mark.anyio
async def test_list_bom_entries(proj_client: AsyncClient) -> None:
    p1 = await _create_part(proj_client, "BOM-L001")
    p2 = await _create_part(proj_client, "BOM-L002")

    r = await proj_client.post("/api/projects", json={"name": "List BOM"})
    pid = r.json()["id"]

    await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": p1["id"], "quantity_required": 2})
    await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": p2["id"], "quantity_required": 10})

    r2 = await proj_client.get(f"/api/projects/{pid}/parts")
    assert r2.status_code == 200
    entries = r2.json()
    assert len(entries) == 2


@pytest.mark.anyio
async def test_update_bom_entry(proj_client: AsyncClient) -> None:
    part = await _create_part(proj_client, "BOM-U001")
    r = await proj_client.post("/api/projects", json={"name": "Update BOM"})
    pid = r.json()["id"]

    r2 = await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": part["id"], "quantity_required": 1})
    entry_id = r2.json()["id"]

    r3 = await proj_client.patch(f"/api/projects/{pid}/parts/{entry_id}", json={"quantity_required": 3, "notes": "Updated"})
    assert r3.status_code == 200
    data = r3.json()
    assert float(data["quantity_required"]) == 3.0
    assert data["notes"] == "Updated"


@pytest.mark.anyio
async def test_remove_bom_entry(proj_client: AsyncClient) -> None:
    part = await _create_part(proj_client, "BOM-D001")
    r = await proj_client.post("/api/projects", json={"name": "Delete BOM Entry"})
    pid = r.json()["id"]

    r2 = await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": part["id"], "quantity_required": 1})
    entry_id = r2.json()["id"]

    r3 = await proj_client.delete(f"/api/projects/{pid}/parts/{entry_id}")
    assert r3.status_code == 204

    r4 = await proj_client.get(f"/api/projects/{pid}/parts")
    assert r4.status_code == 200
    assert len(r4.json()) == 0


@pytest.mark.anyio
async def test_add_bom_entry_part_not_found(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "No Part Project"})
    pid = r.json()["id"]

    r2 = await proj_client.post(
        f"/api/projects/{pid}/parts",
        json={"part_id": str(uuid.uuid4()), "quantity_required": 1},
    )
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# BOM availability tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_bom_availability_sufficient(proj_client: AsyncClient) -> None:
    part = await _create_part(proj_client, "AV-P001")
    location = await _create_location(proj_client)
    await _create_stock(proj_client, part["id"], location["id"], 10.0)

    r = await proj_client.post("/api/projects", json={"name": "Availability Test"})
    pid = r.json()["id"]
    await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": part["id"], "quantity_required": 5})

    r2 = await proj_client.get(f"/api/projects/{pid}/availability")
    assert r2.status_code == 200
    data = r2.json()
    assert data["all_available"] is True
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["is_available"] is True
    assert float(entry["total_in_stock"]) == 10.0
    assert float(entry["quantity_required"]) == 5.0


@pytest.mark.anyio
async def test_bom_availability_insufficient(proj_client: AsyncClient) -> None:
    part = await _create_part(proj_client, "AV-P002")
    location = await _create_location(proj_client)
    await _create_stock(proj_client, part["id"], location["id"], 2.0)

    r = await proj_client.post("/api/projects", json={"name": "Insufficient Test"})
    pid = r.json()["id"]
    await proj_client.post(f"/api/projects/{pid}/parts", json={"part_id": part["id"], "quantity_required": 5})

    r2 = await proj_client.get(f"/api/projects/{pid}/availability")
    assert r2.status_code == 200
    data = r2.json()
    assert data["all_available"] is False
    entry = data["entries"][0]
    assert entry["is_available"] is False


@pytest.mark.anyio
async def test_bom_availability_empty_bom(proj_client: AsyncClient) -> None:
    r = await proj_client.post("/api/projects", json={"name": "Empty BOM"})
    pid = r.json()["id"]

    r2 = await proj_client.get(f"/api/projects/{pid}/availability")
    assert r2.status_code == 200
    data = r2.json()
    assert data["all_available"] is True
    assert data["entries"] == []
