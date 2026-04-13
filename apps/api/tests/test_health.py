"""Tests for the health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_shape(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_database_field_present(client: AsyncClient) -> None:
    """Database field should be present; value depends on connectivity."""
    response = await client.get("/api/health")
    data = response.json()
    assert data["database"] in ("ok", "unavailable")


@pytest.mark.asyncio
async def test_health_version_matches_app(client: AsyncClient) -> None:
    from makervault import __version__

    response = await client.get("/api/health")
    data = response.json()
    assert data["version"] == __version__
