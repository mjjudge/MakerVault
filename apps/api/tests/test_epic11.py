"""Tests for Epic 11 — AI-assisted project inspiration and grounded workflows.

Covers:
- ProjectSuggestion CRUD via /api/suggestions
- Create and run with no active provider → failed with helpful message
- Create and run with mock provider → done with parsed suggestions
- Inventory context includes parts with available stock
- Grounding: inventory parts appear in the AI prompt
- result_json structure validation (suggestions list, owned_parts, missing_parts)
- List suggestions (paginated)
- Get suggestion by ID
- Delete suggestion
- 404 for missing suggestion
- Parse/normalise: malformed AI response (missing 'suggestions' key)
- suggestion_service unit tests (build_inventory_context, _extract_json)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# SQLite in-memory fixtures (Epic-11-specific schema)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def e11_engine():
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
                manufacturer TEXT,
                manufacturer_part_number TEXT,
                package_type TEXT,
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
        await conn.execute(text("""
            CREATE TABLE project_suggestions (
                id TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                provider_id TEXT,
                provider_name TEXT,
                result_json TEXT,
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    yield engine
    await engine.dispose()


@pytest.fixture
async def e11_session(e11_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=e11_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e11_client(e11_session: AsyncSession, tmp_path) -> AsyncClient:
    from httpx import ASGITransport
    from makervault.config import get_settings, Settings

    async def _override_db():
        try:
            yield e11_session
            await e11_session.commit()
        except Exception:
            await e11_session.rollback()
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
    payload = {"part_code": f"E11-{uuid.uuid4().hex[:6]}", "name": "Test Part", "status": "draft"}
    payload.update(kwargs)
    r = await client.post("/api/parts", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_location(client: AsyncClient) -> str:
    r = await client.post("/api/locations", json={"name": "Shelf A"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_stock(client: AsyncClient, part_id: str, location_id: str, qty: float = 5.0) -> str:
    r = await client.post(
        "/api/stock",
        json={"part_id": part_id, "location_id": location_id, "quantity": qty, "status": "available"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _seed_provider(client: AsyncClient) -> str:
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
# Typical mocked AI response
# ---------------------------------------------------------------------------

_MOCK_SUGGESTION_RESPONSE = """{
  "suggestions": [
    {
      "title": "LED Blinker",
      "description": "Use your ESP32 to blink an LED in Morse code.",
      "difficulty": "beginner",
      "owned_parts": [{"part_id": "PLACEHOLDER", "part_name": "ESP32 DevKit"}],
      "missing_parts": [{"name": "LED (5mm red)", "notes": "very cheap"}]
    }
  ]
}"""


# ---------------------------------------------------------------------------
# No active provider → failed suggestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_fails_when_no_provider(e11_client: AsyncClient) -> None:
    r = await e11_client.post(
        "/api/suggestions",
        json={"prompt": "What can I build?"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "failed"
    assert "provider" in data["error_message"].lower()
    assert data["provider_id"] is None


# ---------------------------------------------------------------------------
# Create with mock provider → done
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_suggestion_done(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=_MOCK_SUGGESTION_RESPONSE,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "What can I build with an ESP32?"},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert data["provider_name"] == "Mock Ollama"
    assert "suggestions" in data["result_json"]
    suggestions = data["result_json"]["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["title"] == "LED Blinker"
    assert suggestions[0]["difficulty"] == "beginner"
    assert "owned_parts" in suggestions[0]
    assert "missing_parts" in suggestions[0]


# ---------------------------------------------------------------------------
# Provenance: provider_id and provider_name stored
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_stores_provenance(e11_client: AsyncClient) -> None:
    provider_id = await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=_MOCK_SUGGESTION_RESPONSE,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "project ideas"},
        )

    data = r.json()
    assert data["provider_id"] == provider_id
    assert data["provider_name"] == "Mock Ollama"


# ---------------------------------------------------------------------------
# AI error → failed suggestion with error_message
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_fails_on_ai_error(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Ollama connection refused"),
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "inspire me"},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "failed"
    assert "Ollama" in data["error_message"]


# ---------------------------------------------------------------------------
# Inventory grounding: parts with available stock appear in AI prompt
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_includes_inventory_context(e11_client: AsyncClient) -> None:
    """The inventory context passed to the AI must include stocked parts."""
    await _seed_provider(e11_client)
    loc_id = await _seed_location(e11_client)
    part_id = await _seed_part(e11_client, name="ESP32 DevKit V1")
    await _seed_stock(e11_client, part_id, loc_id, qty=3.0)

    captured_messages: list = []

    async def _capture_complete(messages, options=None):
        captured_messages.extend(messages)
        return _MOCK_SUGGESTION_RESPONSE

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        side_effect=_capture_complete,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "What can I build?"},
        )

    assert r.status_code == 201
    # The inventory context should mention the part name
    all_content = " ".join(m.content for m in captured_messages)
    assert "ESP32 DevKit V1" in all_content
    # Quantity should be mentioned
    assert "3" in all_content


# ---------------------------------------------------------------------------
# Empty inventory → context mentions empty inventory
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_empty_inventory_context(e11_client: AsyncClient) -> None:
    """When no parts have stock, the AI gets an 'empty inventory' context."""
    await _seed_provider(e11_client)

    captured_messages: list = []

    async def _capture_complete(messages, options=None):
        captured_messages.extend(messages)
        return _MOCK_SUGGESTION_RESPONSE

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        side_effect=_capture_complete,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "Suggest something"},
        )

    assert r.status_code == 201
    all_content = " ".join(m.content for m in captured_messages)
    assert "empty" in all_content.lower()


# ---------------------------------------------------------------------------
# Malformed AI response (no 'suggestions' key) → normalised to empty list
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suggestion_normalises_malformed_response(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value='{"ideas": []}',
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "surprise me"},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "done"
    assert data["result_json"] == {"suggestions": []}


# ---------------------------------------------------------------------------
# List suggestions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_suggestions_empty(e11_client: AsyncClient) -> None:
    r = await e11_client.get("/api/suggestions")
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.anyio
async def test_list_suggestions_pagination(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=_MOCK_SUGGESTION_RESPONSE,
    ):
        for i in range(3):
            r = await e11_client.post(
                "/api/suggestions",
                json={"prompt": f"idea {i}"},
            )
            assert r.status_code == 201

    r = await e11_client.get("/api/suggestions")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Pagination: limit=1
    r = await e11_client.get("/api/suggestions?limit=1")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Get a single suggestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_suggestion_by_id(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=_MOCK_SUGGESTION_RESPONSE,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "what to build"},
        )
    suggestion_id = r.json()["id"]

    r2 = await e11_client.get(f"/api/suggestions/{suggestion_id}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == suggestion_id
    assert data["prompt"] == "what to build"


@pytest.mark.anyio
async def test_get_suggestion_404(e11_client: AsyncClient) -> None:
    r = await e11_client.get(f"/api/suggestions/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Delete a suggestion
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_delete_suggestion(e11_client: AsyncClient) -> None:
    await _seed_provider(e11_client)

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.complete",
        new_callable=AsyncMock,
        return_value=_MOCK_SUGGESTION_RESPONSE,
    ):
        r = await e11_client.post(
            "/api/suggestions",
            json={"prompt": "delete me"},
        )
    suggestion_id = r.json()["id"]

    del_r = await e11_client.delete(f"/api/suggestions/{suggestion_id}")
    assert del_r.status_code == 204

    get_r = await e11_client.get(f"/api/suggestions/{suggestion_id}")
    assert get_r.status_code == 404


@pytest.mark.anyio
async def test_delete_suggestion_404(e11_client: AsyncClient) -> None:
    r = await e11_client.delete(f"/api/suggestions/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Prompt validation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_empty_prompt_rejected(e11_client: AsyncClient) -> None:
    r = await e11_client.post(
        "/api/suggestions",
        json={"prompt": ""},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# suggestion_service unit tests
# ---------------------------------------------------------------------------


def test_build_inventory_context_empty():
    from makervault.services.suggestion_service import _build_inventory_context

    ctx = _build_inventory_context([])
    assert "empty" in ctx.lower()


def test_build_inventory_context_with_parts():
    from makervault.services.suggestion_service import _build_inventory_context

    parts = [
        {
            "id": "abc-123",
            "name": "ESP32 DevKit V1",
            "part_kind": "board",
            "short_description": "Wi-Fi+BT microcontroller",
            "manufacturer": "Espressif",
            "tags": ["wifi", "ble"],
            "total_stock": 2.0,
        },
        {
            "id": "def-456",
            "name": "LM7805",
            "part_kind": "component",
            "short_description": None,
            "manufacturer": None,
            "tags": [],
            "total_stock": 10.0,
        },
    ]
    ctx = _build_inventory_context(parts)
    assert "ESP32 DevKit V1" in ctx
    assert "abc-123" in ctx
    assert "2.0" in ctx or "2" in ctx
    assert "LM7805" in ctx
    assert "wifi" in ctx


def test_extract_json_plain():
    from makervault.services.suggestion_service import _extract_json

    result = _extract_json('{"suggestions": []}')
    assert result == {"suggestions": []}


def test_extract_json_with_fence():
    from makervault.services.suggestion_service import _extract_json

    fenced = '```json\n{"suggestions": [{"title": "LED clock"}]}\n```'
    result = _extract_json(fenced)
    assert result["suggestions"][0]["title"] == "LED clock"


def test_build_suggestion_messages_includes_prompt_and_context():
    from makervault.services.suggestion_service import _build_suggestion_messages

    messages = _build_suggestion_messages(
        "What can I build?",
        "Current inventory:\n  • [abc] ESP32 (qty: 3)\n",
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    user_text = messages[1]["content"]
    assert "What can I build?" in user_text
    assert "ESP32" in user_text
