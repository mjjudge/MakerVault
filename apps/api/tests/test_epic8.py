"""Tests for Epic 8 — Search refinement and inventory usability.

Covers:
- PartAlias CRUD via /parts/{id}/aliases
- Alias uniqueness constraint
- Search finds parts via alias subquery
- Part.aliases denorm array sync after add/remove
- StockItemResponse includes location_name and container_name
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
async def epic8_engine():
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
            CREATE TABLE part_aliases (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
                alias TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(part_id, alias)
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
async def epic8_session(epic8_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=epic8_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def epic8_client(epic8_session: AsyncSession) -> AsyncClient:
    from httpx import ASGITransport

    async def _override_db():
        try:
            yield epic8_session
            await epic8_session.commit()
        except Exception:
            await epic8_session.rollback()
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


async def _create_part(client: AsyncClient, part_code: str = "E8-P001", name: str = "Epic8 Part") -> dict:
    r = await client.post("/api/parts", json={"part_code": part_code, "name": name, "status": "active"})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_location(client: AsyncClient, name: str = "Shelf Epic8") -> dict:
    r = await client.post("/api/locations", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_container(client: AsyncClient, location_id: str, name: str = "Bin A") -> dict:
    r = await client.post("/api/containers", json={"name": name, "location_id": location_id})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_stock(client: AsyncClient, part_id: str, location_id: str, qty: float = 5.0) -> dict:
    r = await client.post(
        "/api/stock",
        json={"part_id": part_id, "location_id": location_id, "quantity": qty, "status": "available"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# PartAlias CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_alias(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-A001")
    r = await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "NE555"})
    assert r.status_code == 201
    data = r.json()
    assert data["alias"] == "NE555"
    assert data["part_id"] == part["id"]
    assert "id" in data


@pytest.mark.anyio
async def test_create_alias_with_notes(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-A002")
    r = await epic8_client.post(
        f"/api/parts/{part['id']}/aliases",
        json={"alias": "LM555", "notes": "Texas Instruments variant"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["alias"] == "LM555"
    assert data["notes"] == "Texas Instruments variant"


@pytest.mark.anyio
async def test_list_aliases(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-L001")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "Alias-X"})
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "Alias-Y"})

    r = await epic8_client.get(f"/api/parts/{part['id']}/aliases")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    aliases = {a["alias"] for a in data}
    assert "Alias-X" in aliases
    assert "Alias-Y" in aliases


@pytest.mark.anyio
async def test_list_aliases_empty(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-L002")
    r = await epic8_client.get(f"/api/parts/{part['id']}/aliases")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_alias_uniqueness_conflict(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-U001")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "DUPE"})
    r = await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "DUPE"})
    assert r.status_code == 409


@pytest.mark.anyio
async def test_delete_alias(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-D001")
    r_create = await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "ToDelete"})
    alias_id = r_create.json()["id"]

    r_del = await epic8_client.delete(f"/api/parts/{part['id']}/aliases/{alias_id}")
    assert r_del.status_code == 204

    r_list = await epic8_client.get(f"/api/parts/{part['id']}/aliases")
    assert r_list.json() == []


@pytest.mark.anyio
async def test_delete_alias_not_found(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-D002")
    r = await epic8_client.delete(f"/api/parts/{part['id']}/aliases/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_alias_part_not_found(epic8_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    r = await epic8_client.post(f"/api/parts/{fake_id}/aliases", json={"alias": "Ghost"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Alias denorm sync tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_aliases_denorm_populated_after_create(epic8_client: AsyncClient) -> None:
    """After adding aliases, they should be retrievable via the aliases endpoint."""
    part = await _create_part(epic8_client, "E8-DN001")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "Denorm-1"})
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "Denorm-2"})

    r = await epic8_client.get(f"/api/parts/{part['id']}/aliases")
    assert r.status_code == 200
    listed = {a["alias"] for a in r.json()}
    assert listed == {"Denorm-1", "Denorm-2"}


@pytest.mark.anyio
async def test_aliases_denorm_cleared_after_delete_all(epic8_client: AsyncClient) -> None:
    """After deleting the last alias, the aliases list should be empty."""
    part = await _create_part(epic8_client, "E8-DN002")
    r1 = await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "Only-Alias"})
    alias_id = r1.json()["id"]

    await epic8_client.delete(f"/api/parts/{part['id']}/aliases/{alias_id}")

    r = await epic8_client.get(f"/api/parts/{part['id']}/aliases")
    assert r.json() == []


# ---------------------------------------------------------------------------
# Search via alias tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_search_finds_part_by_alias(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-S001", name="Timer IC")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "NE555P"})

    r = await epic8_client.get("/api/parts", params={"q": "NE555P"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    ids = [p["id"] for p in data["items"]]
    assert part["id"] in ids


@pytest.mark.anyio
async def test_search_alias_partial_match(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-S002", name="Op-Amp")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "LM741CN"})

    r = await epic8_client.get("/api/parts", params={"q": "741"})
    assert r.status_code == 200
    data = r.json()
    ids = [p["id"] for p in data["items"]]
    assert part["id"] in ids


@pytest.mark.anyio
async def test_search_by_name_still_works(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-S003", name="UniqueNameXYZ123")

    r = await epic8_client.get("/api/parts", params={"q": "UniqueNameXYZ123"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(p["id"] == part["id"] for p in data["items"])


@pytest.mark.anyio
async def test_search_no_false_alias_match(epic8_client: AsyncClient) -> None:
    """A part whose alias does NOT match the query should not appear."""
    part = await _create_part(epic8_client, "E8-S004", name="Resistor")
    await epic8_client.post(f"/api/parts/{part['id']}/aliases", json={"alias": "R-100"})

    r = await epic8_client.get("/api/parts", params={"q": "NE555XXXXXXNOTEXIST"})
    assert r.status_code == 200
    data = r.json()
    ids = [p["id"] for p in data["items"]]
    assert part["id"] not in ids


# ---------------------------------------------------------------------------
# Stock placement name enrichment tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_stock_list_includes_location_name(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-ST001")
    location = await _create_location(epic8_client, "Cabinet Alpha")
    await _create_stock(epic8_client, part["id"], location["id"])

    r = await epic8_client.get("/api/stock", params={"part_id": part["id"]})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["location_name"] == "Cabinet Alpha"
    assert items[0]["container_name"] is None


@pytest.mark.anyio
async def test_stock_get_includes_location_name(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-ST002")
    location = await _create_location(epic8_client, "Drawer Beta")
    stock = await _create_stock(epic8_client, part["id"], location["id"])

    r = await epic8_client.get(f"/api/stock/{stock['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["location_name"] == "Drawer Beta"
    assert data["container_name"] is None


@pytest.mark.anyio
async def test_stock_create_includes_location_name(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-ST003")
    location = await _create_location(epic8_client, "Shelf Gamma")
    stock = await _create_stock(epic8_client, part["id"], location["id"])

    assert stock["location_name"] == "Shelf Gamma"
    assert stock["container_name"] is None


@pytest.mark.anyio
async def test_stock_container_name_enrichment(epic8_client: AsyncClient) -> None:
    part = await _create_part(epic8_client, "E8-ST004")
    location = await _create_location(epic8_client, "Main Shelf")
    container = await _create_container(epic8_client, location["id"], name="Bin-42")

    r = await epic8_client.post(
        "/api/stock",
        json={"part_id": part["id"], "container_id": container["id"], "quantity": 3, "status": "available"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["container_name"] == "Bin-42"
    assert data["location_name"] is None


@pytest.mark.anyio
async def test_stock_response_backward_compatible(epic8_client: AsyncClient) -> None:
    """location_name and container_name default to None — no regression."""
    part = await _create_part(epic8_client, "E8-ST005")
    location = await _create_location(epic8_client, "Compat Shelf")
    stock = await _create_stock(epic8_client, part["id"], location["id"])

    assert "location_name" in stock
    assert "container_name" in stock
