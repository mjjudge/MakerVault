"""Tests for Epic 16 — Backup, restore metadata, and operational resilience.

Covers:
- BackupRecord model creation and persistence
- GET /api/backup/status — empty database returns nulls
- GET /api/backup/status — reflects most-recent record correctly
- GET /api/backup/records — returns all records, ordered newest-first
- POST /api/backup/trigger — creates a BackupRecord in the database
- POST /api/backup/trigger — records failure when backup tool unavailable
- POST /api/backup/prune — deletes archives beyond retention count
- POST /api/backup/prune — respects backup_type filter
- POST /api/backup/prune — no-op when retention disabled (count=0)
- GET /api/backup/restore-checklist — returns plain-text content
- Config: backup_path and backup_retention_count are readable from settings
- backup_service.prune_backups — deletes only records beyond retention
- backup_service.run_db_backup — raises RuntimeError when pg_dump missing
- backup_service.run_documents_backup — raises RuntimeError when source missing
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from makervault.config import Settings, get_settings
from makervault.database import get_db_session
from makervault.main import app
from makervault.services.backup_service import (
    prune_backups,
    run_db_backup,
    run_documents_backup,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

_DDL = """
CREATE TABLE backup_records (
    id TEXT PRIMARY KEY,
    backup_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    file_path TEXT,
    file_size_bytes INTEGER,
    triggered_by TEXT NOT NULL DEFAULT 'manual',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def e16_engine():
    engine = create_async_engine(SQLITE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text(_DDL))
    yield engine
    await engine.dispose()


@pytest.fixture
async def e16_session(e16_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        bind=e16_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def e16_client(e16_session: AsyncSession):
    async def _override_db():
        yield e16_session

    app.dependency_overrides[get_db_session] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def _insert_record(
    session: AsyncSession,
    *,
    backup_type: str = "full",
    status: str = "success",
    started_at: datetime | None = None,
    file_path: str | None = "/backups/test.tar.gz",
    file_size_bytes: int | None = 1024,
    error_message: str | None = None,
    triggered_by: str = "manual",
) -> str:
    rid = str(uuid.uuid4())
    at = started_at or _utcnow()
    await session.execute(
        text("""
            INSERT INTO backup_records
              (id, backup_type, status, started_at, finished_at,
               file_path, file_size_bytes, triggered_by, error_message)
            VALUES
              (:id, :bt, :st, :sa, :fa, :fp, :fsb, :tb, :em)
        """),
        {
            "id": rid,
            "bt": backup_type,
            "st": status,
            "sa": at.isoformat(),
            "fa": at.isoformat() if status != "running" else None,
            "fp": file_path if status == "success" else None,
            "fsb": file_size_bytes if status == "success" else None,
            "tb": triggered_by,
            "em": error_message,
        },
    )
    await session.flush()
    return rid


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_config_backup_path_default():
    """backup_path has a sensible default."""
    s = Settings()
    assert s.backup_path == "/data/makervault/backups"


def test_config_backup_retention_count_default():
    """backup_retention_count defaults to 10."""
    s = Settings()
    assert s.backup_retention_count == 10


def test_config_backup_path_override(monkeypatch):
    """backup_path can be overridden via environment variable."""
    monkeypatch.setenv("BACKUP_PATH", "/mnt/backups/makervault")
    get_settings.cache_clear()
    s = Settings()
    assert s.backup_path == "/mnt/backups/makervault"
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# GET /api/backup/status — empty database
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_backup_status_empty(e16_client: AsyncClient):
    resp = await e16_client.get("/api/backup/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_successful_db_backup"] is None
    assert data["last_successful_documents_backup"] is None
    assert data["last_successful_full_backup"] is None
    assert data["last_backup_status"] is None
    assert data["total_records"] == 0


# ---------------------------------------------------------------------------
# GET /api/backup/status — with data
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_backup_status_with_records(
    e16_client: AsyncClient, e16_session: AsyncSession
):
    await _insert_record(e16_session, backup_type="db", status="success")
    await _insert_record(e16_session, backup_type="documents", status="success")
    await _insert_record(e16_session, backup_type="full", status="failed", error_message="disk full")

    resp = await e16_client.get("/api/backup/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_successful_db_backup"] is not None
    assert data["last_successful_documents_backup"] is not None
    assert data["last_successful_full_backup"] is None  # full was failed
    assert data["last_backup_error"] == "disk full"
    assert data["total_records"] == 3


# ---------------------------------------------------------------------------
# GET /api/backup/records
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_backup_records_ordered(
    e16_client: AsyncClient, e16_session: AsyncSession
):
    from datetime import timedelta

    now = _utcnow()
    await _insert_record(e16_session, started_at=now - timedelta(hours=2))
    await _insert_record(e16_session, started_at=now - timedelta(hours=1))
    await _insert_record(e16_session, started_at=now)

    resp = await e16_client.get("/api/backup/records")
    assert resp.status_code == 200
    records = resp.json()
    assert len(records) == 3
    # Confirm newest-first ordering
    times = [r["started_at"] for r in records]
    assert times == sorted(times, reverse=True)


@pytest.mark.anyio
async def test_list_backup_records_pagination(
    e16_client: AsyncClient, e16_session: AsyncSession
):
    for _ in range(5):
        await _insert_record(e16_session)

    resp = await e16_client.get("/api/backup/records?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp2 = await e16_client.get("/api/backup/records?limit=2&offset=2")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2


# ---------------------------------------------------------------------------
# POST /api/backup/trigger
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_trigger_backup_records_success(
    e16_client: AsyncClient, e16_session: AsyncSession, tmp_path: Path
):
    """Trigger a db backup; mock run_db_backup to avoid needing pg_dump."""
    fake_file = str(tmp_path / "test.dump")
    Path(fake_file).write_bytes(b"fake dump content")

    with patch(
        "makervault.services.backup_service.run_db_backup",
        return_value=(fake_file, 17),
    ):
        # Override settings to use tmp_path
        orig_settings = get_settings()

        def _mock_settings():
            return Settings(
                backup_path=str(tmp_path),
                database_url=orig_settings.database_url,
                document_store_path=orig_settings.document_store_path,
                secret_key=orig_settings.secret_key,
            )

        app.dependency_overrides[get_settings] = _mock_settings
        resp = await e16_client.post(
            "/api/backup/trigger", json={"backup_type": "db"}
        )
        app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 202
    data = resp.json()
    assert data["backup_type"] == "db"
    assert data["status"] == "success"
    assert "record_id" in data


@pytest.mark.anyio
async def test_trigger_backup_records_failure(
    e16_client: AsyncClient, e16_session: AsyncSession, tmp_path: Path
):
    """When the backup tool fails, status is 'failed' and error is recorded."""
    with patch(
        "makervault.services.backup_service.run_db_backup",
        side_effect=RuntimeError("pg_dump: command not found"),
    ):
        orig_settings = get_settings()

        def _mock_settings():
            return Settings(
                backup_path=str(tmp_path),
                database_url=orig_settings.database_url,
                document_store_path=orig_settings.document_store_path,
                secret_key=orig_settings.secret_key,
            )

        app.dependency_overrides[get_settings] = _mock_settings
        resp = await e16_client.post(
            "/api/backup/trigger", json={"backup_type": "db"}
        )
        app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "failed"
    assert "pg_dump" in data["message"]


# ---------------------------------------------------------------------------
# POST /api/backup/prune
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_prune_removes_old_records(
    e16_client: AsyncClient, e16_session: AsyncSession, tmp_path: Path
):
    """Prune removes records beyond retention; kept count matches retention."""
    # Create 5 success records for "db"
    from datetime import timedelta
    now = _utcnow()
    for i in range(5):
        fake_path = str(tmp_path / f"backup_{i}.dump")
        Path(fake_path).write_bytes(b"x" * 100)
        await _insert_record(
            e16_session,
            backup_type="db",
            status="success",
            started_at=now - timedelta(hours=5 - i),
            file_path=fake_path,
            file_size_bytes=100,
        )

    orig_settings = get_settings()

    def _mock_settings():
        return Settings(
            backup_path=str(tmp_path),
            backup_retention_count=3,
            database_url=orig_settings.database_url,
            document_store_path=orig_settings.document_store_path,
            secret_key=orig_settings.secret_key,
        )

    app.dependency_overrides[get_settings] = _mock_settings
    resp = await e16_client.post("/api/backup/prune?backup_type=db")
    app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] == 2
    assert data["kept_count"] == 3
    assert data["freed_bytes"] == 200  # 2 × 100 bytes


@pytest.mark.anyio
async def test_prune_noop_when_disabled(
    e16_client: AsyncClient, e16_session: AsyncSession, tmp_path: Path
):
    """Prune is a no-op when retention_count is 0."""
    from datetime import timedelta
    now = _utcnow()
    for i in range(3):
        await _insert_record(
            e16_session,
            backup_type="full",
            started_at=now - timedelta(hours=i),
        )

    orig_settings = get_settings()

    def _mock_settings():
        return Settings(
            backup_path=str(tmp_path),
            backup_retention_count=0,
            database_url=orig_settings.database_url,
            document_store_path=orig_settings.document_store_path,
            secret_key=orig_settings.secret_key,
        )

    app.dependency_overrides[get_settings] = _mock_settings
    resp = await e16_client.post("/api/backup/prune")
    app.dependency_overrides.pop(get_settings, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] == 0
    assert "disabled" in data["message"].lower()


# ---------------------------------------------------------------------------
# GET /api/backup/restore-checklist
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_restore_checklist_returns_plaintext(e16_client: AsyncClient):
    resp = await e16_client.get("/api/backup/restore-checklist")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "MakerVault" in body
    assert "pg_restore" in body
    assert "Step 1" in body
    assert "Step 5" in body
    assert "Content-Disposition" in resp.headers


# ---------------------------------------------------------------------------
# backup_service unit tests
# ---------------------------------------------------------------------------


def test_run_db_backup_raises_when_pg_dump_missing(tmp_path: Path):
    """run_db_backup raises RuntimeError when pg_dump is not available."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "pg_dump: command not found"
        mock_run.return_value = mock_result

        with pytest.raises(RuntimeError, match="pg_dump"):
            run_db_backup(str(tmp_path), "postgresql+asyncpg://u:p@localhost/db")


def test_run_documents_backup_raises_when_source_missing(tmp_path: Path):
    """run_documents_backup raises RuntimeError when the source dir is absent."""
    with pytest.raises(RuntimeError, match="does not exist"):
        run_documents_backup(str(tmp_path), "/nonexistent/path/documents")


@pytest.mark.anyio
async def test_prune_backups_service(e16_session: AsyncSession, tmp_path: Path):
    """prune_backups deletes oldest success records beyond retention."""
    from datetime import timedelta

    settings = Settings(
        backup_path=str(tmp_path),
        backup_retention_count=2,
        secret_key="x",
    )
    now = _utcnow()

    # Insert 4 success records
    for i in range(4):
        fake_file = tmp_path / f"b_{i}.dump"
        fake_file.write_bytes(b"z" * 50)
        await _insert_record(
            e16_session,
            backup_type="db",
            status="success",
            started_at=now - timedelta(hours=4 - i),
            file_path=str(fake_file),
            file_size_bytes=50,
        )

    # Insert 1 failed record — should not be pruned
    await _insert_record(
        e16_session,
        backup_type="db",
        status="failed",
        started_at=now - timedelta(hours=10),
        file_path=None,
        file_size_bytes=None,
    )

    deleted, kept, freed = await prune_backups(e16_session, settings, backup_type="db")

    assert deleted == 2
    assert kept == 2
    assert freed == 100  # 2 × 50 bytes
