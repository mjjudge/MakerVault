"""Tests for Epic 9 — AI provider abstraction.

Covers:
- AIProviderConfig CRUD via /api/ai/providers
- Name uniqueness constraint
- base_url requirement for ollama / openai_compatible
- Default provider management (only one default at a time)
- Health-check endpoint (mocked, no real network calls)
- Provider factory (build_provider)
- Secret resolution — no key value is ever returned by the API
- get_active_provider returns the default enabled provider
- Tests confirming no secrets are persisted in DB records
"""

import os
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# Fixtures — SQLite in-memory schema (mirrors 0005 migration)
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def epic9_engine():
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
    yield engine
    await engine.dispose()


@pytest.fixture
async def epic9_session(epic9_engine) -> AsyncSession:
    factory = async_sessionmaker(
        bind=epic9_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def epic9_client(epic9_session: AsyncSession) -> AsyncClient:
    from httpx import ASGITransport

    async def _override_db():
        try:
            yield epic9_session
            await epic9_session.commit()
        except Exception:
            await epic9_session.rollback()
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


async def _create_openai(client: AsyncClient, name: str = "My OpenAI", **kwargs) -> dict:
    payload = {
        "name": name,
        "provider_type": "openai",
        "model": "gpt-4o",
        "api_key_env_var": "OPENAI_API_KEY",
        **kwargs,
    }
    r = await client.post("/api/ai/providers", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _create_ollama(client: AsyncClient, name: str = "Local Ollama", **kwargs) -> dict:
    payload = {
        "name": name,
        "provider_type": "ollama",
        "base_url": "http://ollama:11434",
        "model": "llama3",
        **kwargs,
    }
    r = await client.post("/api/ai/providers", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_openai_provider(epic9_client: AsyncClient) -> None:
    data = await _create_openai(epic9_client)
    assert data["name"] == "My OpenAI"
    assert data["provider_type"] == "openai"
    assert data["model"] == "gpt-4o"
    assert data["api_key_env_var"] == "OPENAI_API_KEY"
    assert data["is_enabled"] is True
    assert data["is_default"] is False
    assert "id" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_create_ollama_provider(epic9_client: AsyncClient) -> None:
    data = await _create_ollama(epic9_client)
    assert data["name"] == "Local Ollama"
    assert data["provider_type"] == "ollama"
    assert data["base_url"] == "http://ollama:11434"
    assert data["api_key_env_var"] is None


@pytest.mark.anyio
async def test_list_providers_empty(epic9_client: AsyncClient) -> None:
    r = await epic9_client.get("/api/ai/providers")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_list_providers(epic9_client: AsyncClient) -> None:
    await _create_openai(epic9_client, "Provider A")
    await _create_ollama(epic9_client, "Provider B")

    r = await epic9_client.get("/api/ai/providers")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert {"Provider A", "Provider B"} == names


@pytest.mark.anyio
async def test_get_provider(epic9_client: AsyncClient) -> None:
    created = await _create_openai(epic9_client)
    r = await epic9_client.get(f"/api/ai/providers/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.anyio
async def test_get_provider_not_found(epic9_client: AsyncClient) -> None:
    r = await epic9_client.get(f"/api/ai/providers/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_update_provider(epic9_client: AsyncClient) -> None:
    created = await _create_openai(epic9_client)
    r = await epic9_client.patch(
        f"/api/ai/providers/{created['id']}",
        json={"model": "gpt-4o-mini", "notes": "Cheaper model"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["model"] == "gpt-4o-mini"
    assert data["notes"] == "Cheaper model"
    assert data["name"] == "My OpenAI"  # unchanged


@pytest.mark.anyio
async def test_delete_provider(epic9_client: AsyncClient) -> None:
    created = await _create_openai(epic9_client)
    r = await epic9_client.delete(f"/api/ai/providers/{created['id']}")
    assert r.status_code == 204

    r2 = await epic9_client.get(f"/api/ai/providers/{created['id']}")
    assert r2.status_code == 404


@pytest.mark.anyio
async def test_delete_provider_not_found(epic9_client: AsyncClient) -> None:
    r = await epic9_client.delete(f"/api/ai/providers/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Uniqueness / validation tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_name_uniqueness_conflict(epic9_client: AsyncClient) -> None:
    await _create_openai(epic9_client, "Duplicate Name")
    r = await epic9_client.post(
        "/api/ai/providers",
        json={"name": "Duplicate Name", "provider_type": "openai", "model": "gpt-4o"},
    )
    assert r.status_code == 409


@pytest.mark.anyio
async def test_ollama_requires_base_url(epic9_client: AsyncClient) -> None:
    r = await epic9_client.post(
        "/api/ai/providers",
        json={"name": "Bad Ollama", "provider_type": "ollama", "model": "llama3"},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_openai_compatible_requires_base_url(epic9_client: AsyncClient) -> None:
    r = await epic9_client.post(
        "/api/ai/providers",
        json={"name": "Bad Compat", "provider_type": "openai_compatible", "model": "custom"},
    )
    assert r.status_code == 422


@pytest.mark.anyio
async def test_unknown_provider_type_rejected(epic9_client: AsyncClient) -> None:
    r = await epic9_client.post(
        "/api/ai/providers",
        json={"name": "Unknown", "provider_type": "magic_ai", "model": "model-x"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Default-provider management
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_only_one_default_at_a_time(epic9_client: AsyncClient) -> None:
    p1 = await _create_openai(epic9_client, "OpenAI Default", is_default=True)
    assert p1["is_default"] is True

    # Creating a second provider as default should demote the first.
    p2 = await _create_ollama(epic9_client, "Ollama Default", is_default=True)
    assert p2["is_default"] is True

    # Re-fetch p1 and confirm it is no longer default.
    r = await epic9_client.get(f"/api/ai/providers/{p1['id']}")
    assert r.json()["is_default"] is False


@pytest.mark.anyio
async def test_patch_sets_default_and_demotes_others(epic9_client: AsyncClient) -> None:
    p1 = await _create_openai(epic9_client, "First Provider", is_default=True)
    p2 = await _create_ollama(epic9_client, "Second Provider")

    await epic9_client.patch(f"/api/ai/providers/{p2['id']}", json={"is_default": True})

    r1 = await epic9_client.get(f"/api/ai/providers/{p1['id']}")
    assert r1.json()["is_default"] is False

    r2 = await epic9_client.get(f"/api/ai/providers/{p2['id']}")
    assert r2.json()["is_default"] is True


# ---------------------------------------------------------------------------
# Secrets-not-persisted tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_api_key_value_never_returned(epic9_client: AsyncClient) -> None:
    """The response must contain api_key_env_var (the name), not a key value."""
    provider = await _create_openai(epic9_client, api_key_env_var="OPENAI_API_KEY")
    # Only the env var NAME is returned, not any actual secret value.
    assert provider["api_key_env_var"] == "OPENAI_API_KEY"
    # No field in the response should contain an actual key format.
    assert "sk-" not in str(provider)


@pytest.mark.anyio
async def test_local_provider_has_no_api_key_env_var(epic9_client: AsyncClient) -> None:
    provider = await _create_ollama(epic9_client)
    assert provider["api_key_env_var"] is None


# ---------------------------------------------------------------------------
# Health-check endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health_check_healthy(epic9_client: AsyncClient) -> None:
    provider = await _create_ollama(epic9_client, "HealthyOllama")

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.health_check",
        new_callable=AsyncMock,
        return_value=True,
    ):
        r = await epic9_client.post(f"/api/ai/providers/{provider['id']}/health")

    assert r.status_code == 200
    data = r.json()
    assert data["healthy"] is True
    assert data["provider_name"] == "HealthyOllama"


@pytest.mark.anyio
async def test_health_check_unhealthy(epic9_client: AsyncClient) -> None:
    provider = await _create_ollama(epic9_client, "DeadOllama")

    with patch(
        "makervault.ai.adapters.ollama_adapter.OllamaProvider.health_check",
        new_callable=AsyncMock,
        return_value=False,
    ):
        r = await epic9_client.post(f"/api/ai/providers/{provider['id']}/health")

    assert r.status_code == 200
    data = r.json()
    assert data["healthy"] is False
    assert data["detail"] is not None


@pytest.mark.anyio
async def test_health_check_missing_env_var(epic9_client: AsyncClient) -> None:
    """When the required API key env var is missing, health check returns unhealthy."""
    provider = await _create_openai(
        epic9_client, "NoKeyProvider", api_key_env_var="NONEXISTENT_KEY_XYZ"
    )
    # Ensure the env var is not set.
    os.environ.pop("NONEXISTENT_KEY_XYZ", None)

    r = await epic9_client.post(f"/api/ai/providers/{provider['id']}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["healthy"] is False
    assert "NONEXISTENT_KEY_XYZ" in data["detail"]


@pytest.mark.anyio
async def test_health_check_not_found(epic9_client: AsyncClient) -> None:
    r = await epic9_client.post(f"/api/ai/providers/{uuid.uuid4()}/health")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Provider factory tests
# ---------------------------------------------------------------------------


def test_build_provider_openai() -> None:
    from makervault.ai.service import build_provider
    from makervault.ai.adapters.openai_adapter import OpenAIProvider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test OpenAI",
        provider_type="openai",
        model="gpt-4o",
        api_key_env_var=None,
        is_enabled=True,
        is_default=False,
    )
    provider = build_provider(config)
    assert isinstance(provider, OpenAIProvider)


def test_build_provider_ollama() -> None:
    from makervault.ai.service import build_provider
    from makervault.ai.adapters.ollama_adapter import OllamaProvider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Test Ollama",
        provider_type="ollama",
        base_url="http://localhost:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=False,
    )
    provider = build_provider(config)
    assert isinstance(provider, OllamaProvider)


def test_build_provider_openai_compatible() -> None:
    from makervault.ai.service import build_provider
    from makervault.ai.adapters.openai_adapter import OpenAIProvider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="vLLM",
        provider_type="openai_compatible",
        base_url="http://vllm:8000",
        model="meta-llama/Meta-Llama-3-8B-Instruct",
        api_key_env_var=None,
        is_enabled=True,
        is_default=False,
    )
    provider = build_provider(config)
    assert isinstance(provider, OpenAIProvider)


def test_build_provider_unknown_type_raises() -> None:
    from makervault.ai.service import build_provider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Mystery",
        provider_type="unknown_type",
        model="model",
        api_key_env_var=None,
        is_enabled=True,
        is_default=False,
    )
    with pytest.raises(ValueError, match="Unknown AI provider type"):
        build_provider(config)


def test_api_key_resolved_from_env() -> None:
    """build_provider resolves the key from the environment — no hard-coding."""
    from makervault.ai.service import build_provider
    from makervault.models.ai_provider_config import AIProviderConfig

    os.environ["TEST_OPENAI_KEY"] = "sk-test-1234"
    try:
        config = AIProviderConfig(
            id=uuid.uuid4(),
            name="KeyTest",
            provider_type="openai",
            model="gpt-4o",
            api_key_env_var="TEST_OPENAI_KEY",
            is_enabled=True,
            is_default=False,
        )
        provider = build_provider(config)
        assert provider._api_key == "sk-test-1234"
    finally:
        del os.environ["TEST_OPENAI_KEY"]


def test_missing_api_key_env_var_raises() -> None:
    from makervault.ai.service import build_provider
    from makervault.models.ai_provider_config import AIProviderConfig

    os.environ.pop("DEFINITELY_NOT_SET_KEY", None)
    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="MissingKey",
        provider_type="openai",
        model="gpt-4o",
        api_key_env_var="DEFINITELY_NOT_SET_KEY",
        is_enabled=True,
        is_default=False,
    )
    with pytest.raises(EnvironmentError, match="DEFINITELY_NOT_SET_KEY"):
        build_provider(config)


# ---------------------------------------------------------------------------
# get_active_provider tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_active_provider_returns_none_when_empty(epic9_session: AsyncSession) -> None:
    from makervault.ai.service import get_active_provider
    result = await get_active_provider(epic9_session)
    assert result is None


@pytest.mark.anyio
async def test_get_active_provider_returns_default(epic9_session: AsyncSession) -> None:
    from makervault.ai.service import get_active_provider, build_provider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Default Ollama",
        provider_type="ollama",
        base_url="http://ollama:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=True,
        is_default=True,
    )
    epic9_session.add(config)
    await epic9_session.flush()

    provider = await get_active_provider(epic9_session)
    assert provider is not None
    assert provider.config.name == "Default Ollama"


@pytest.mark.anyio
async def test_get_active_provider_skips_disabled(epic9_session: AsyncSession) -> None:
    from makervault.ai.service import get_active_provider
    from makervault.models.ai_provider_config import AIProviderConfig

    config = AIProviderConfig(
        id=uuid.uuid4(),
        name="Disabled Ollama",
        provider_type="ollama",
        base_url="http://ollama:11434",
        model="llama3",
        api_key_env_var=None,
        is_enabled=False,
        is_default=True,
    )
    epic9_session.add(config)
    await epic9_session.flush()

    result = await get_active_provider(epic9_session)
    assert result is None
