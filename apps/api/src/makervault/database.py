"""Async SQLAlchemy engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from makervault.config import Settings, get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def build_engine(settings: Settings | None = None):
    """Create and return an async SQLAlchemy engine.

    Args:
        settings: Optional Settings instance. Defaults to the cached singleton.
    """
    if settings is None:
        settings = get_settings()

    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


def build_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Return an async session factory bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# ---------------------------------------------------------------------------
# Module-level engine and factory (initialised lazily on first import).
# Replaced during testing by conftest fixtures.
# ---------------------------------------------------------------------------
_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """Return the module-level engine, creating it if necessary."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory, creating it if necessary."""
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = build_session_factory(get_engine())
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
