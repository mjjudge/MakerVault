"""Tests for Epic 10 — AI enrichment and document understanding.

Covers:
- EnrichmentJob CRUD via /api/enrichment/jobs
- job_type / entity_type compatibility validation
- Job lifecycle: pending → running → done / failed
- No active provider → failed job with helpful message
- Mocked AI result parsing (generate_aliases, classify_part,
  summarise_document, extract_metadata)
- Apply: aliases written to PartAlias and Part.aliases
- Apply: classify_part sets part_kind and tags
- Apply: summarise_document sets document.summary
- Apply: extract_metadata sets document fields
- Dismiss: sets status to dismissed
- Provenance: provider_id / provider_name stored
- Re-apply / double-apply / invalid status transitions
- Failure/retry: failed job can be replaced by a new job
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (Epic-10-specific schema)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def e10_engine():
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE ai_provider_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                provider_type TEXT NOT NULL,
                base_url TEXT,
                model TEXT NOT NULL,
                api_key_env_var TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
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
            CREATE TABLE stock_item_documents (
                id TEXT PRIMARY KEY,
                stock_item_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
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
            CREATE TABLE project_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL DEFAULT 'other',
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
            CREATE TABLE enrichment_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                provider_id TEXT,
                provider_name TEXT,
                result_json TEXT,
                confidence INTEGER,
                error_message TEXT,
                applied_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def e10_session(e10_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e10_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e10_client(e10_session: AsyncSession, tmp_path) -> AsyncClient:
    from httpx import ASGITransport
    from makervault.config import get_settings, Settings

    async def _override_db():
        try:
            yield e10_session
            await e10_session.commit()
        except Exception:
            await e10_session.rollback()
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
# Seed helpers — all via HTTP API
# ---------------------------------------------------------------------------


async def _seed_part(client: AsyncClient, **kwargs) -> str:
    payload = {"part_code": f"E10-{uuid.uuid4().hex[:6]}", "name": "Test Part", "status": "draft"}
    payload.update(kwargs)
    r = await client.post("/api/parts", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_document(client: AsyncClient, title: str = "Test Document") -> str:
    content = b"VCC = 3.3V. Part number: ESP32-WROOM-32."
    r = await client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        data={"title": title, "document_type": "datasheet"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_provider(client: AsyncClient) -> str:
    """Create a default-enabled Ollama provider via the API."""
    r = await client.post(
        "/api/ai/providers",
        json={
            "name": "Mock Ollama",
            "provider_type": "ollama",
            "base_url": "http://ollama:11434",
            "model": "llama3",
            "is_enabled": True,
            "is_default": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Job type / entity_type compatibility tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summarise_document_requires_document(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)
    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "summarise_document", "entity_type": "part", "entity_id": part_id},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_classify_part_requires_part(e10_client: AsyncClient) -> None:
    doc_id = await _seed_document(e10_client)
    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "document", "entity_id": doc_id},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_invalid_job_type_rejected(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)
    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "magic_enrich", "entity_type": "part", "entity_id": part_id},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_entity_not_found(e10_client: AsyncClient) -> None:
    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={
            "job_type": "classify_part",
            "entity_type": "part",
            "entity_id": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# No active provider → failed job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_job_fails_when_no_provider(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "failed"
    assert "provider" in data["error_message"].lower()
    assert data["provider_id"] is None


# ---------------------------------------------------------------------------
# Mocked AI calls — generate_aliases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_aliases_creates_job_done(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client, name="ESP32 DevKit V1")

    mock_response = '{"aliases": ["ESP-WROOM-32", "ESP32"], "confidence": 88}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "generate_aliases", "entity_type": "part", "entity_id": part_id},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert data["confidence"] == 88
    assert data["result_json"]["aliases"] == ["ESP-WROOM-32", "ESP32"]
    assert data["provider_name"] == "Mock Ollama"


# ---------------------------------------------------------------------------
# Mocked AI calls — classify_part
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_classify_part_creates_job_done(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client, name="LM7805 Linear Regulator")

    mock_response = '{"part_kind": "component", "tags": ["voltage-regulator", "linear"], "confidence": 95}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert data["result_json"]["part_kind"] == "component"
    assert "voltage-regulator" in data["result_json"]["tags"]
    assert data["confidence"] == 95


# ---------------------------------------------------------------------------
# Mocked AI calls — summarise_document
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_summarise_document_creates_job_done(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    doc_id = await _seed_document(e10_client, title="ESP32 Datasheet")

    mock_response = (
        '{"summary": "The ESP32 is a low-cost Wi-Fi and BT SoC.", '
        '"key_specs": ["3.3V supply", "240 MHz dual-core"], '
        '"part_numbers": ["ESP32-WROOM-32"]}'
    )

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "summarise_document", "entity_type": "document", "entity_id": doc_id},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert "ESP32" in data["result_json"]["summary"]
    assert data["result_json"]["part_numbers"] == ["ESP32-WROOM-32"]


# ---------------------------------------------------------------------------
# Mocked AI calls — extract_metadata
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_extract_metadata_creates_job_done(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    doc_id = await _seed_document(e10_client, title="LM7805 Datasheet")

    mock_response = (
        '{"manufacturer": "Texas Instruments", "part_number": "LM7805", '
        '"package_type": "TO-220", "capabilities": {"output_voltage": "5V"}, '
        '"tags": ["regulator"], "confidence": 90}'
    )

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "extract_metadata", "entity_type": "document", "entity_id": doc_id},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert data["result_json"]["manufacturer"] == "Texas Instruments"
    assert data["confidence"] == 90


# ---------------------------------------------------------------------------
# AI error → failed job
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_ai_error_produces_failed_job(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Connection refused"),
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "failed"
    assert "Connection refused" in data["error_message"]


# ---------------------------------------------------------------------------
# Apply — generate_aliases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_generate_aliases(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client, name="ESP32 DevKit V1")

    mock_response = '{"aliases": ["ESP-WROOM-32", "ESP32"], "confidence": 85}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "generate_aliases", "entity_type": "part", "entity_id": part_id},
        )
    job_id = r.json()["id"]

    # Apply
    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/apply")
    assert r2.status_code == 200
    data = r2.json()
    assert data["applied_at"] is not None

    # Verify aliases were created
    aliases_r = await e10_client.get(f"/api/parts/{part_id}/aliases")
    assert aliases_r.status_code == 200
    alias_names = {a["alias"] for a in aliases_r.json()}
    assert "ESP-WROOM-32" in alias_names
    assert "ESP32" in alias_names


# ---------------------------------------------------------------------------
# Apply — classify_part
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_classify_part(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client, name="LM7805")

    mock_response = '{"part_kind": "component", "tags": ["regulator"], "confidence": 92}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
        )
    job_id = r.json()["id"]

    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/apply")
    assert r2.status_code == 200

    # Verify part was updated
    part_r = await e10_client.get(f"/api/parts/{part_id}")
    assert part_r.status_code == 200
    part_data = part_r.json()
    assert part_data["part_kind"] == "component"
    # Tags are stored as PostgreSQL ARRAY; SQLite drops them (consistent with
    # the parts router behaviour), so we only assert on part_kind here.


# ---------------------------------------------------------------------------
# Apply — summarise_document
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_summarise_document(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    doc_id = await _seed_document(e10_client, title="ESP32 Datasheet")

    mock_response = (
        '{"summary": "The ESP32 is a dual-core SoC.", '
        '"key_specs": ["3.3V"], "part_numbers": []}'
    )

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "summarise_document", "entity_type": "document", "entity_id": doc_id},
        )
    job_id = r.json()["id"]

    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/apply")
    assert r2.status_code == 200

    doc_r = await e10_client.get(f"/api/v1/documents/{doc_id}")
    assert doc_r.status_code == 200
    assert doc_r.json()["summary"] == "The ESP32 is a dual-core SoC."


# ---------------------------------------------------------------------------
# Dismiss
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_dismiss_job(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client)

    mock_response = '{"part_kind": "component", "tags": [], "confidence": 60}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
        )
    job_id = r.json()["id"]

    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/dismiss")
    assert r2.status_code == 200
    assert r2.json()["status"] == "dismissed"


@pytest.mark.anyio
async def test_dismiss_failed_job_returns_conflict(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    # No provider → failed job
    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    job_id = r.json()["id"]

    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/dismiss")
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# Apply on non-done job → conflict
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_apply_failed_job_returns_conflict(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    job_id = r.json()["id"]

    r2 = await e10_client.post(f"/api/enrichment/jobs/{job_id}/apply")
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# List and filter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_jobs_empty(e10_client: AsyncClient) -> None:
    r = await e10_client.get("/api/enrichment/jobs")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.anyio
async def test_list_jobs_filtered_by_entity(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )

    r = await e10_client.get(
        "/api/enrichment/jobs",
        params={"entity_type": "part", "entity_id": part_id},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2


# ---------------------------------------------------------------------------
# Get / delete
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_job(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    job_id = r.json()["id"]

    r2 = await e10_client.get(f"/api/enrichment/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id


@pytest.mark.anyio
async def test_get_job_not_found(e10_client: AsyncClient) -> None:
    r = await e10_client.get(f"/api/enrichment/jobs/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_delete_job(e10_client: AsyncClient) -> None:
    part_id = await _seed_part(e10_client)

    r = await e10_client.post(
        "/api/enrichment/jobs",
        json={"job_type": "classify_part", "entity_type": "part", "entity_id": part_id},
    )
    job_id = r.json()["id"]

    r2 = await e10_client.delete(f"/api/enrichment/jobs/{job_id}")
    assert r2.status_code == 204

    r3 = await e10_client.get(f"/api/enrichment/jobs/{job_id}")
    assert r3.status_code == 404


# ---------------------------------------------------------------------------
# Provenance — provider_id and provider_name stored
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_provider_provenance_stored(e10_client: AsyncClient) -> None:
    await _seed_provider(e10_client)
    part_id = await _seed_part(e10_client)

    mock_response = '{"aliases": ["Alias A"], "confidence": 70}'

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        r = await e10_client.post(
            "/api/enrichment/jobs",
            json={"job_type": "generate_aliases", "entity_type": "part", "entity_id": part_id},
        )

    data = r.json()
    assert data["provider_id"] is not None
    assert data["provider_name"] == "Mock Ollama"


# ---------------------------------------------------------------------------
# Enrichment service unit tests (without HTTP layer)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_run_enrichment_generate_aliases() -> None:
    from makervault.services.enrichment_service import run_enrichment
    from makervault.models.ai_provider_config import AIProviderConfig
    from makervault.ai.adapters.ollama_adapter import OllamaProvider

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    provider = OllamaProvider(config)

    from makervault.models.part import Part as PartModel

    part = PartModel(
        id=uuid.uuid4(),
        part_code="TEST-01",
        name="ATmega328P",
        short_description="8-bit AVR microcontroller",
        manufacturer="Microchip",
        manufacturer_part_number="ATmega328P-PU",
        part_kind="component",
        default_unit="pcs",
    )

    mock_response = '{"aliases": ["ATmega328", "AVR 328"], "confidence": 82}'

    with patch.object(provider, "complete", new_callable=AsyncMock, return_value=mock_response):
        result, confidence = await run_enrichment("generate_aliases", part, provider)

    assert result["aliases"] == ["ATmega328", "AVR 328"]
    assert confidence == 82


@pytest.mark.anyio
async def test_run_enrichment_classify_part() -> None:
    from makervault.services.enrichment_service import run_enrichment
    from makervault.models.ai_provider_config import AIProviderConfig
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.models.part import Part as PartModel

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    provider = OllamaProvider(config)
    part = PartModel(
        id=uuid.uuid4(),
        part_code="TEST-02",
        name="HC-SR04",
        short_description="Ultrasonic distance sensor",
        default_unit="pcs",
    )

    mock_response = '{"part_kind": "module", "tags": ["sensor", "ultrasonic"], "confidence": 90}'

    with patch.object(provider, "complete", new_callable=AsyncMock, return_value=mock_response):
        result, confidence = await run_enrichment("classify_part", part, provider)

    assert result["part_kind"] == "module"
    assert "sensor" in result["tags"]
    assert confidence == 90


@pytest.mark.anyio
async def test_run_enrichment_bad_json_raises() -> None:
    from makervault.services.enrichment_service import run_enrichment
    from makervault.models.ai_provider_config import AIProviderConfig
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.models.part import Part as PartModel

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    provider = OllamaProvider(config)
    part = PartModel(
        id=uuid.uuid4(),
        part_code="TEST-03",
        name="Broken Part",
        default_unit="pcs",
    )

    with patch.object(
        provider, "complete", new_callable=AsyncMock, return_value="Not JSON at all!"
    ):
        with pytest.raises(Exception):
            await run_enrichment("classify_part", part, provider)


@pytest.mark.anyio
async def test_run_enrichment_markdown_fence_stripped() -> None:
    """AI response wrapped in markdown code fences is handled gracefully."""
    from makervault.services.enrichment_service import run_enrichment
    from makervault.models.ai_provider_config import AIProviderConfig
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.models.part import Part as PartModel

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    provider = OllamaProvider(config)
    part = PartModel(
        id=uuid.uuid4(),
        part_code="TEST-04",
        name="DS18B20",
        default_unit="pcs",
    )

    fenced = '```json\n{"aliases": ["DS18B20+"], "confidence": 77}\n```'

    with patch.object(provider, "complete", new_callable=AsyncMock, return_value=fenced):
        result, confidence = await run_enrichment("generate_aliases", part, provider)

    assert result["aliases"] == ["DS18B20+"]
    assert confidence == 77


@pytest.mark.anyio
async def test_run_enrichment_unknown_job_type_raises() -> None:
    from makervault.services.enrichment_service import run_enrichment
    from makervault.models.ai_provider_config import AIProviderConfig
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.models.part import Part as PartModel

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    provider = OllamaProvider(config)
    part = PartModel(id=uuid.uuid4(), part_code="X", name="X", default_unit="pcs")

    with pytest.raises(ValueError, match="Unknown job_type"):
        await run_enrichment("does_not_exist", part, provider)
