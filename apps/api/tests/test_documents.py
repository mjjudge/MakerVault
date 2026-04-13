"""Tests for Epic 6 — Documents and local knowledge capture.

Covers:
- Document upload and storage
- SHA-256 checksum computation
- Document metadata persistence
- Part-document linking
- StockItem-document linking
- Project-document linking
- Document list and get endpoints
- Document update and delete
"""

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app
from makervault.services.document_store import (
    build_storage_path,
    compute_sha256,
    save_document,
    delete_document_file,
)

# ---------------------------------------------------------------------------
# Fixtures — SQLite in-memory schema
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def doc_engine():
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
async def doc_session(doc_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=doc_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def doc_client(doc_session: AsyncSession, tmp_path) -> AsyncClient:
    from httpx import ASGITransport
    from makervault.config import get_settings, Settings

    async def _override_db():
        try:
            yield doc_session
            await doc_session.commit()
        except Exception:
            await doc_session.rollback()
            raise

    def _override_settings():
        return Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            document_store_path=str(tmp_path / "docs"),
        )

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_settings] = _override_settings
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# document_store unit tests
# ---------------------------------------------------------------------------


def test_compute_sha256_known_value():
    data = b"hello world"
    expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576fbb641adeef67b41"
    # standard sha256 of "hello world"
    import hashlib
    assert compute_sha256(data) == hashlib.sha256(data).hexdigest()


def test_compute_sha256_empty():
    import hashlib
    assert compute_sha256(b"") == hashlib.sha256(b"").hexdigest()


def test_build_storage_path():
    doc_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    path = build_storage_path(doc_id, "test.pdf")
    assert path.startswith("12/34/")
    assert "test.pdf" in path
    assert str(doc_id) in path


def test_save_document(tmp_path):
    doc_id = uuid.uuid4()
    data = b"PDF content here"
    rel_path, checksum, size = save_document(str(tmp_path), doc_id, "doc.pdf", data)
    assert size == len(data)
    assert len(checksum) == 64  # SHA-256 hex digest
    assert checksum == compute_sha256(data)
    # File should exist
    full_path = tmp_path / rel_path
    assert full_path.exists()
    assert full_path.read_bytes() == data


def test_delete_document_file(tmp_path):
    doc_id = uuid.uuid4()
    data = b"to be deleted"
    rel_path, _, _ = save_document(str(tmp_path), doc_id, "delete_me.pdf", data)
    full_path = tmp_path / rel_path
    assert full_path.exists()
    delete_document_file(str(tmp_path), rel_path)
    assert not full_path.exists()


def test_delete_nonexistent_file_is_safe(tmp_path):
    # Should not raise
    delete_document_file(str(tmp_path), "nonexistent/path/file.pdf")


# ---------------------------------------------------------------------------
# API tests — document upload and metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_document(doc_client: AsyncClient) -> None:
    file_data = b"This is a test PDF"
    r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("datasheet.pdf", io.BytesIO(file_data), "application/pdf")},
        data={"title": "ESP32 Datasheet", "document_type": "datasheet"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "ESP32 Datasheet"
    assert data["document_type"] == "datasheet"
    assert data["source_type"] == "uploaded"
    assert data["checksum"] is not None
    assert len(data["checksum"]) == 64
    assert data["file_size_bytes"] == len(file_data)
    assert data["mime_type"] == "application/pdf"


@pytest.mark.asyncio
async def test_upload_document_checksum_matches(doc_client: AsyncClient) -> None:
    import hashlib
    content = b"Checksum verification content"
    r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("notes.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Notes"},
    )
    assert r.status_code == 201
    assert r.json()["checksum"] == hashlib.sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_list_documents_empty(doc_client: AsyncClient) -> None:
    r = await doc_client.get("/api/v1/documents")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_documents(doc_client: AsyncClient) -> None:
    for i in range(3):
        await doc_client.post(
            "/api/v1/documents/upload",
            files={"file": (f"file{i}.pdf", io.BytesIO(b"data"), "application/pdf")},
            data={"title": f"Doc {i}"},
        )
    r = await doc_client.get("/api/v1/documents")
    assert r.status_code == 200
    assert r.json()["total"] == 3


@pytest.mark.asyncio
async def test_get_document(doc_client: AsyncClient) -> None:
    r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("manual.pdf", io.BytesIO(b"manual data"), "application/pdf")},
        data={"title": "User Manual"},
    )
    doc_id = r.json()["id"]
    r2 = await doc_client.get(f"/api/v1/documents/{doc_id}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "User Manual"


@pytest.mark.asyncio
async def test_get_document_not_found(doc_client: AsyncClient) -> None:
    r = await doc_client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_document(doc_client: AsyncClient) -> None:
    r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")},
        data={"title": "Original Title"},
    )
    doc_id = r.json()["id"]
    r2 = await doc_client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"title": "Updated Title", "summary": "A brief summary"},
    )
    assert r2.status_code == 200
    assert r2.json()["title"] == "Updated Title"
    assert r2.json()["summary"] == "A brief summary"


@pytest.mark.asyncio
async def test_delete_document(doc_client: AsyncClient) -> None:
    r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("delete.pdf", io.BytesIO(b"delete me"), "application/pdf")},
        data={"title": "To Delete"},
    )
    doc_id = r.json()["id"]
    r2 = await doc_client.delete(f"/api/v1/documents/{doc_id}")
    assert r2.status_code == 204
    r3 = await doc_client.get(f"/api/v1/documents/{doc_id}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_search_documents_by_title(doc_client: AsyncClient) -> None:
    await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("a.pdf", io.BytesIO(b"a"), "application/pdf")},
        data={"title": "ESP32 Pinout Diagram"},
    )
    await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("b.pdf", io.BytesIO(b"b"), "application/pdf")},
        data={"title": "Arduino Manual"},
    )
    r = await doc_client.get("/api/v1/documents?q=ESP32")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert "ESP32" in r.json()["items"][0]["title"]


# ---------------------------------------------------------------------------
# API tests — Part ↔ Document linking
# ---------------------------------------------------------------------------


@pytest.fixture
async def part_and_doc(doc_client: AsyncClient):
    """Create a part and a document for linking tests."""
    part_r = await doc_client.post(
        "/api/parts", json={"part_code": "DOC-TEST-001", "name": "Doc Test Part"}
    )
    part_id = part_r.json()["id"]

    doc_r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("ds.pdf", io.BytesIO(b"datasheet"), "application/pdf")},
        data={"title": "Test Datasheet", "document_type": "datasheet"},
    )
    doc_id = doc_r.json()["id"]
    return {"part_id": part_id, "doc_id": doc_id}


@pytest.mark.asyncio
async def test_link_document_to_part(doc_client: AsyncClient, part_and_doc) -> None:
    r = await doc_client.post(
        f"/api/v1/parts/{part_and_doc['part_id']}/documents",
        json={
            "document_id": part_and_doc["doc_id"],
            "relationship_type": "primary_datasheet",
            "is_primary": True,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["part_id"] == part_and_doc["part_id"]
    assert data["document_id"] == part_and_doc["doc_id"]
    assert data["relationship_type"] == "primary_datasheet"
    assert data["is_primary"] is True
    assert data["document"]["title"] == "Test Datasheet"


@pytest.mark.asyncio
async def test_list_part_documents(doc_client: AsyncClient, part_and_doc) -> None:
    await doc_client.post(
        f"/api/v1/parts/{part_and_doc['part_id']}/documents",
        json={"document_id": part_and_doc["doc_id"]},
    )
    r = await doc_client.get(f"/api/v1/parts/{part_and_doc['part_id']}/documents")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["document_id"] == part_and_doc["doc_id"]


@pytest.mark.asyncio
async def test_unlink_document_from_part(doc_client: AsyncClient, part_and_doc) -> None:
    link_r = await doc_client.post(
        f"/api/v1/parts/{part_and_doc['part_id']}/documents",
        json={"document_id": part_and_doc["doc_id"]},
    )
    link_id = link_r.json()["id"]
    r = await doc_client.delete(
        f"/api/v1/parts/{part_and_doc['part_id']}/documents/{link_id}"
    )
    assert r.status_code == 204
    r2 = await doc_client.get(f"/api/v1/parts/{part_and_doc['part_id']}/documents")
    assert len(r2.json()) == 0


@pytest.mark.asyncio
async def test_link_document_to_nonexistent_part(doc_client: AsyncClient, part_and_doc) -> None:
    r = await doc_client.post(
        f"/api/v1/parts/{uuid.uuid4()}/documents",
        json={"document_id": part_and_doc["doc_id"]},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# API tests — StockItem ↔ Document linking
# ---------------------------------------------------------------------------


@pytest.fixture
async def stock_and_doc(doc_client: AsyncClient):
    """Create a location, part, stock item, and document."""
    loc_r = await doc_client.post("/api/locations", json={"name": "Doc Test Shelf"})
    loc_id = loc_r.json()["id"]
    part_r = await doc_client.post(
        "/api/parts", json={"part_code": "DOC-STOCK-001", "name": "Stock Doc Part"}
    )
    part_id = part_r.json()["id"]
    stock_r = await doc_client.post(
        "/api/stock",
        json={"part_id": part_id, "location_id": loc_id, "quantity": 5},
    )
    stock_id = stock_r.json()["id"]
    doc_r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("receipt.pdf", io.BytesIO(b"receipt"), "application/pdf")},
        data={"title": "Purchase Receipt", "document_type": "receipt"},
    )
    doc_id = doc_r.json()["id"]
    return {"stock_id": stock_id, "doc_id": doc_id}


@pytest.mark.asyncio
async def test_link_document_to_stock_item(doc_client: AsyncClient, stock_and_doc) -> None:
    r = await doc_client.post(
        f"/api/v1/stock/{stock_and_doc['stock_id']}/documents",
        json={"document_id": stock_and_doc["doc_id"], "notes": "Purchase receipt"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["stock_item_id"] == stock_and_doc["stock_id"]
    assert data["document"]["title"] == "Purchase Receipt"


@pytest.mark.asyncio
async def test_list_stock_item_documents(doc_client: AsyncClient, stock_and_doc) -> None:
    await doc_client.post(
        f"/api/v1/stock/{stock_and_doc['stock_id']}/documents",
        json={"document_id": stock_and_doc["doc_id"]},
    )
    r = await doc_client.get(f"/api/v1/stock/{stock_and_doc['stock_id']}/documents")
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_unlink_document_from_stock_item(
    doc_client: AsyncClient, stock_and_doc
) -> None:
    link_r = await doc_client.post(
        f"/api/v1/stock/{stock_and_doc['stock_id']}/documents",
        json={"document_id": stock_and_doc["doc_id"]},
    )
    link_id = link_r.json()["id"]
    r = await doc_client.delete(
        f"/api/v1/stock/{stock_and_doc['stock_id']}/documents/{link_id}"
    )
    assert r.status_code == 204


# ---------------------------------------------------------------------------
# API tests — Project ↔ Document linking
# ---------------------------------------------------------------------------


@pytest.fixture
async def project_and_doc(doc_client: AsyncClient, doc_session: AsyncSession):
    """Insert a project directly and upload a document."""
    from makervault.models.project import Project
    project = Project(name="Test Project", status="active")
    doc_session.add(project)
    await doc_session.flush()
    await doc_session.commit()
    project_id = str(project.id)

    doc_r = await doc_client.post(
        "/api/v1/documents/upload",
        files={"file": ("wiring.pdf", io.BytesIO(b"wiring notes"), "application/pdf")},
        data={"title": "Wiring Notes", "document_type": "project_note"},
    )
    doc_id = doc_r.json()["id"]
    return {"project_id": project_id, "doc_id": doc_id}


@pytest.mark.asyncio
async def test_link_document_to_project(
    doc_client: AsyncClient, project_and_doc
) -> None:
    r = await doc_client.post(
        f"/api/v1/projects/{project_and_doc['project_id']}/documents",
        json={
            "document_id": project_and_doc["doc_id"],
            "relationship_type": "wiring_note",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["project_id"] == project_and_doc["project_id"]
    assert data["relationship_type"] == "wiring_note"
    assert data["document"]["title"] == "Wiring Notes"


@pytest.mark.asyncio
async def test_list_project_documents(
    doc_client: AsyncClient, project_and_doc
) -> None:
    await doc_client.post(
        f"/api/v1/projects/{project_and_doc['project_id']}/documents",
        json={"document_id": project_and_doc["doc_id"]},
    )
    r = await doc_client.get(
        f"/api/v1/projects/{project_and_doc['project_id']}/documents"
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_unlink_document_from_project(
    doc_client: AsyncClient, project_and_doc
) -> None:
    link_r = await doc_client.post(
        f"/api/v1/projects/{project_and_doc['project_id']}/documents",
        json={"document_id": project_and_doc["doc_id"]},
    )
    link_id = link_r.json()["id"]
    r = await doc_client.delete(
        f"/api/v1/projects/{project_and_doc['project_id']}/documents/{link_id}"
    )
    assert r.status_code == 204
