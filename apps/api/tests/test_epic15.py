"""Tests for Epic 15 — Inventory hygiene dashboard and part merge workflow.

Covers:
- GET /api/hygiene/dashboard:  returns expected shape
- GET /api/hygiene/dashboard:  parts missing documents appear in list
- GET /api/hygiene/dashboard:  parts missing aliases appear in list
- GET /api/hygiene/dashboard:  parts missing capabilities appear in list
- GET /api/hygiene/dashboard:  parts with split stock appear in list
- GET /api/hygiene/dashboard:  duplicate groups are detected
- GET /api/hygiene/dashboard:  part with all data present is clean
- POST /parts/{id}/merge:      stock items re-parented to target
- POST /parts/{id}/merge:      document links re-parented (dup skipped)
- POST /parts/{id}/merge:      alias entries re-parented (dup skipped)
- POST /parts/{id}/merge:      project parts re-parented (dup removed)
- POST /parts/{id}/merge:      source part is archived
- POST /parts/{id}/merge:      response contains correct counts
- POST /parts/{id}/merge:      merge self → 422
- POST /parts/{id}/merge:      unknown source → 404
- POST /parts/{id}/merge:      unknown target → 404
"""

from __future__ import annotations

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
async def e15_engine():
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
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'other',
                source_type TEXT NOT NULL DEFAULT 'upload',
                source_url TEXT,
                local_path TEXT,
                mime_type TEXT,
                checksum TEXT,
                file_size_bytes INTEGER,
                text_extracted TEXT,
                summary TEXT,
                version_label TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE part_documents (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL DEFAULT 'other',
                is_primary INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await conn.execute(text("""
            CREATE TABLE part_aliases (
                id TEXT PRIMARY KEY,
                part_id TEXT NOT NULL,
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
                status TEXT NOT NULL DEFAULT 'planning',
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
    yield engine
    await engine.dispose()


@pytest.fixture
async def e15_session(e15_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e15_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e15_client(e15_session: AsyncSession) -> AsyncClient:
    async def _override_db():
        try:
            yield e15_session
            await e15_session.commit()
        except Exception:
            await e15_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


# ---------------------------------------------------------------------------
# Insert helpers
#
# NOTE: The PostgreSQL UUID(as_uuid=True) bind_processor converts UUID objects
# to their hex (no-hyphen) representation on SQLite.  Test rows must therefore
# be stored WITHOUT hyphens so that ORM WHERE-by-uuid comparisons match.
# Helpers return the standard hyphenated str(uuid) for use in assertions that
# compare against JSON API responses (which Pydantic always emits as hyphenated).
# ---------------------------------------------------------------------------


def _hex(s: str | uuid.UUID) -> str:
    """Return the no-hyphen hex form of a UUID string or object."""
    if isinstance(s, uuid.UUID):
        return s.hex
    return uuid.UUID(s).hex


async def _insert_part(
    session: AsyncSession,
    *,
    part_id: str | None = None,
    part_code: str,
    name: str,
    manufacturer_part_number: str | None = None,
    capabilities_json: str | None = None,
    status: str = "active",
) -> str:
    pid = uuid.UUID(part_id) if part_id else uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO parts (id, part_code, name, manufacturer_part_number, "
            "capabilities_json, is_active, status) "
            "VALUES (:id, :pc, :name, :mpn, :caps, 1, :status)"
        ),
        {
            "id": pid.hex,
            "pc": part_code,
            "name": name,
            "mpn": manufacturer_part_number,
            "caps": capabilities_json,
            "status": status,
        },
    )
    await session.commit()
    return str(pid)


async def _insert_document(session: AsyncSession, title: str) -> str:
    doc = uuid.uuid4()
    await session.execute(
        text("INSERT INTO documents (id, title) VALUES (:id, :title)"),
        {"id": doc.hex, "title": title},
    )
    await session.commit()
    return str(doc)


async def _link_document(session: AsyncSession, part_id: str, doc_id: str) -> str:
    link = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO part_documents (id, part_id, document_id) "
            "VALUES (:id, :pid, :did)"
        ),
        {"id": link.hex, "pid": _hex(part_id), "did": _hex(doc_id)},
    )
    await session.commit()
    return str(link)


async def _insert_alias(session: AsyncSession, part_id: str, alias: str) -> str:
    alias_row = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO part_aliases (id, part_id, alias) VALUES (:id, :pid, :alias)"
        ),
        {"id": alias_row.hex, "pid": _hex(part_id), "alias": alias},
    )
    await session.commit()
    return str(alias_row)


async def _insert_location(session: AsyncSession, name: str) -> str:
    loc = uuid.uuid4()
    await session.execute(
        text("INSERT INTO locations (id, name) VALUES (:id, :name)"),
        {"id": loc.hex, "name": name},
    )
    await session.commit()
    return str(loc)


async def _insert_stock(
    session: AsyncSession,
    part_id: str,
    *,
    location_id: str | None = None,
    container_id: str | None = None,
    qty: float = 5,
    status: str = "available",
) -> str:
    si = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO stock_items (id, part_id, location_id, container_id, quantity, status) "
            "VALUES (:id, :pid, :lid, :cid, :qty, :status)"
        ),
        {
            "id": si.hex,
            "pid": _hex(part_id),
            "lid": _hex(location_id) if location_id else None,
            "cid": _hex(container_id) if container_id else None,
            "qty": qty,
            "status": status,
        },
    )
    await session.commit()
    return str(si)


async def _insert_project(session: AsyncSession, name: str) -> str:
    proj = uuid.uuid4()
    await session.execute(
        text("INSERT INTO projects (id, name) VALUES (:id, :name)"),
        {"id": proj.hex, "name": name},
    )
    await session.commit()
    return str(proj)


async def _insert_project_part(
    session: AsyncSession, project_id: str, part_id: str, qty: float = 1
) -> str:
    pp = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO project_parts (id, project_id, part_id, quantity_required) "
            "VALUES (:id, :proj, :part, :qty)"
        ),
        {"id": pp.hex, "proj": _hex(project_id), "part": _hex(part_id), "qty": qty},
    )
    await session.commit()
    return str(pp)


# ===========================================================================
# GET /api/hygiene/dashboard
# ===========================================================================


@pytest.mark.anyio
async def test_dashboard_returns_shape(e15_client):
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "parts_missing_documents" in data
    assert "parts_missing_aliases" in data
    assert "parts_missing_capabilities" in data
    assert "split_stock_parts" in data
    assert "duplicate_groups" in data


@pytest.mark.anyio
async def test_dashboard_detects_missing_documents(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="NODOC-001", name="No Doc Part")
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_documents"]]
    assert pid in ids


@pytest.mark.anyio
async def test_dashboard_excludes_part_with_document(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="HASDOC-001", name="Has Doc Part")
    doc_id = await _insert_document(e15_session, "Test Datasheet")
    await _link_document(e15_session, pid, doc_id)
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_documents"]]
    assert pid not in ids


@pytest.mark.anyio
async def test_dashboard_detects_missing_aliases(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="NOALIAS-001", name="No Alias Part")
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_aliases"]]
    assert pid in ids


@pytest.mark.anyio
async def test_dashboard_excludes_part_with_alias(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="HASALIAS-001", name="Has Alias Part")
    await _insert_alias(e15_session, pid, "my-alias")
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_aliases"]]
    assert pid not in ids


@pytest.mark.anyio
async def test_dashboard_detects_missing_capabilities(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="NOCAP-001", name="No Cap Part")
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_capabilities"]]
    assert pid in ids


@pytest.mark.anyio
async def test_dashboard_excludes_part_with_capabilities(e15_client, e15_session):
    pid = await _insert_part(
        e15_session,
        part_code="HASCAP-001",
        name="Has Cap Part",
        capabilities_json='{"voltage": "3.3V"}',
    )
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()["parts_missing_capabilities"]]
    assert pid not in ids


@pytest.mark.anyio
async def test_dashboard_detects_split_stock(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="SPLIT-001", name="Split Stock Part")
    loc1 = await _insert_location(e15_session, "Drawer A")
    loc2 = await _insert_location(e15_session, "Drawer B")
    await _insert_stock(e15_session, pid, location_id=loc1)
    await _insert_stock(e15_session, pid, location_id=loc2)
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    split_ids = [p["id"] for p in resp.json()["split_stock_parts"]]
    assert pid in split_ids


@pytest.mark.anyio
async def test_dashboard_no_split_for_single_location(e15_client, e15_session):
    pid = await _insert_part(e15_session, part_code="NOSPLIT-001", name="Single Location Part")
    loc = await _insert_location(e15_session, "Shelf C")
    await _insert_stock(e15_session, pid, location_id=loc)
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    split_ids = [p["id"] for p in resp.json()["split_stock_parts"]]
    assert pid not in split_ids


@pytest.mark.anyio
async def test_dashboard_detects_duplicates(e15_client, e15_session):
    await _insert_part(e15_session, part_code="DUP-A-001", name="Duplicate Part")
    await _insert_part(e15_session, part_code="DUP-A-002", name="Duplicate Part")
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    groups = resp.json()["duplicate_groups"]
    assert len(groups) >= 1
    # Both parts should appear in at least one group
    all_group_codes = [
        p["part_code"]
        for g in groups
        for p in g["parts"]
    ]
    assert "DUP-A-001" in all_group_codes
    assert "DUP-A-002" in all_group_codes


@pytest.mark.anyio
async def test_dashboard_empty_inventory(e15_client):
    resp = await e15_client.get("/api/hygiene/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["parts_missing_documents"] == []
    assert data["parts_missing_aliases"] == []
    assert data["parts_missing_capabilities"] == []
    assert data["split_stock_parts"] == []
    assert data["duplicate_groups"] == []


# ===========================================================================
# POST /api/parts/{id}/merge
# ===========================================================================


@pytest.mark.anyio
async def test_merge_moves_stock_items(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-001", name="Source Part")
    target_id = await _insert_part(e15_session, part_code="TGT-001", name="Target Part")
    loc = await _insert_location(e15_session, "Shelf X")
    await _insert_stock(e15_session, source_id, location_id=loc)
    await _insert_stock(e15_session, source_id, location_id=loc)

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_items_moved"] == 2
    assert data["source_archived"] is True

    # Verify in DB — ORM stores part_id as hex, so compare using hex form
    from sqlalchemy import text as t
    result = await e15_session.execute(
        t("SELECT part_id FROM stock_items")
    )
    part_ids = [r[0] for r in result.fetchall()]
    target_hex = _hex(target_id)
    assert all(pid == target_hex for pid in part_ids)


@pytest.mark.anyio
async def test_merge_moves_document_links(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-002", name="Source 2")
    target_id = await _insert_part(e15_session, part_code="TGT-002", name="Target 2")
    doc_id = await _insert_document(e15_session, "Datasheet")
    await _link_document(e15_session, source_id, doc_id)

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["document_links_moved"] == 1


@pytest.mark.anyio
async def test_merge_deduplicates_document_links(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-003", name="Source 3")
    target_id = await _insert_part(e15_session, part_code="TGT-003", name="Target 3")
    doc_id = await _insert_document(e15_session, "Shared Datasheet")
    # Both source and target already linked to the same document
    await _link_document(e15_session, source_id, doc_id)
    await _link_document(e15_session, target_id, doc_id)

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    # The duplicate should be skipped, not double-linked
    assert resp.json()["document_links_moved"] == 0


@pytest.mark.anyio
async def test_merge_moves_aliases(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-004", name="Source 4")
    target_id = await _insert_part(e15_session, part_code="TGT-004", name="Target 4")
    await _insert_alias(e15_session, source_id, "alias-x")

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["aliases_moved"] == 1


@pytest.mark.anyio
async def test_merge_deduplicates_aliases(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-005", name="Source 5")
    target_id = await _insert_part(e15_session, part_code="TGT-005", name="Target 5")
    # Both have the same alias
    await _insert_alias(e15_session, source_id, "shared-alias")
    await _insert_alias(e15_session, target_id, "shared-alias")

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["aliases_moved"] == 0


@pytest.mark.anyio
async def test_merge_moves_project_parts(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-006", name="Source 6")
    target_id = await _insert_part(e15_session, part_code="TGT-006", name="Target 6")
    proj_id = await _insert_project(e15_session, "Project Alpha")
    await _insert_project_part(e15_session, proj_id, source_id)

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["project_parts_moved"] == 1


@pytest.mark.anyio
async def test_merge_deduplicates_project_parts(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-007", name="Source 7")
    target_id = await _insert_part(e15_session, part_code="TGT-007", name="Target 7")
    proj_id = await _insert_project(e15_session, "Project Beta")
    # Both source and target are already in the BOM for the same project
    await _insert_project_part(e15_session, proj_id, source_id)
    await _insert_project_part(e15_session, proj_id, target_id)

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["project_parts_moved"] == 0


@pytest.mark.anyio
async def test_merge_archives_source(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-008", name="Source 8")
    target_id = await _insert_part(e15_session, part_code="TGT-008", name="Target 8")

    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 200
    assert resp.json()["source_archived"] is True

    from sqlalchemy import text as t
    row = (
        await e15_session.execute(
            t("SELECT status, is_active FROM parts WHERE id = :id"),
            {"id": _hex(source_id)},
        )
    ).fetchone()
    assert row is not None
    assert row[0] == "archived"
    assert row[1] == 0


@pytest.mark.anyio
async def test_merge_self_returns_422(e15_client, e15_session):
    part_id = await _insert_part(e15_session, part_code="SELF-001", name="Self Part")
    resp = await e15_client.post(
        f"/api/parts/{part_id}/merge",
        json={"target_part_id": part_id},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_merge_unknown_source_returns_404(e15_client, e15_session):
    target_id = await _insert_part(e15_session, part_code="TGT-X01", name="Target X")
    ghost_id = str(uuid.uuid4())
    resp = await e15_client.post(
        f"/api/parts/{ghost_id}/merge",
        json={"target_part_id": target_id},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_merge_unknown_target_returns_404(e15_client, e15_session):
    source_id = await _insert_part(e15_session, part_code="SRC-X01", name="Source X")
    ghost_id = str(uuid.uuid4())
    resp = await e15_client.post(
        f"/api/parts/{source_id}/merge",
        json={"target_part_id": ghost_id},
    )
    assert resp.status_code == 404
