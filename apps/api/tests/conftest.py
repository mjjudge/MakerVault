"""Pytest configuration and shared fixtures for MakerVault API tests.

Uses an in-memory SQLite database for database tests so no PostgreSQL instance
is required when running the test suite locally.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from makervault.database import get_db_session
from makervault.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite engine for isolated database tests
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine():
    """Create a fresh in-memory SQLite engine per test.

    Schema creation is intentionally omitted here because models use
    PostgreSQL-specific types (JSONB, TSVECTOR, ARRAY) that SQLite cannot
    render.  Tests that need tables should create their own SQLite-compatible
    DDL directly (see test_models.py for the pattern).
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncSession:
    """Yield a test database session connected to the in-memory engine."""
    factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession):
    """Async test client with the DB dependency overridden to use SQLite."""

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
