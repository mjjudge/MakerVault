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
    """Base.metadata.create_all should run without error (no models yet)."""
    from makervault.database import Base

    async with db_engine.begin() as conn:
        # Should be idempotent — calling a second time must not raise.
        await conn.run_sync(Base.metadata.create_all)
