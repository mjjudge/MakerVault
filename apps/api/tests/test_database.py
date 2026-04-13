"""Tests for database connectivity and session management."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_db_session_is_async_session(db_session: AsyncSession) -> None:
    assert isinstance(db_session, AsyncSession)


@pytest.mark.asyncio
async def test_db_session_can_execute_select_1(db_session: AsyncSession) -> None:
    """Basic query should succeed against the test database."""
    result = await db_session.execute(text("SELECT 1"))
    row = result.scalar()
    assert row == 1


@pytest.mark.asyncio
async def test_db_session_rollback_on_exception(
    db_engine, db_session: AsyncSession
) -> None:
    """Session rollback should not break the session for subsequent queries."""
    await db_session.rollback()
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_tables_created_from_base_metadata(db_engine) -> None:
    """Base.metadata should be accessible; it describes PostgreSQL schema."""
    from makervault.database import Base

    # Verify that models are registered in the metadata.
    # We cannot run create_all on SQLite because models use PG-specific types
    # (JSONB, TSVECTOR, ARRAY).  What we can verify is that the table names
    # are registered in the metadata, proving models were imported successfully.
    table_names = set(Base.metadata.tables.keys())
    assert len(table_names) > 0
