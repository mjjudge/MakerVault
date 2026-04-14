"""Backup service for MakerVault (Epic 16).

This module contains the logic for:
- Running PostgreSQL database dumps (via ``pg_dump``)
- Archiving the document store directory (via ``tar``)
- Pruning old backup archives to recover disk space

All operations are synchronous (run in a thread pool via ``asyncio.to_thread``
where needed) and record their outcome in the ``backup_records`` table so that
the backup status is always visible through the API.

Design notes
------------
* Backups are written to the directory configured via ``settings.backup_path``.
  This is mounted as a Docker volume and can be pointed at a separate physical
  disk by replacing the named volume with a bind mount in ``docker-compose.yml``.
* Archive filenames are timestamped to the second so concurrent runs produce
  distinct files.
* ``pg_dump`` is used for database backups; the ``DATABASE_URL`` environment
  variable is parsed to extract the connection details.  The dump is written in
  PostgreSQL custom format (``-Fc``) for compact size and full restore support.
* Documents are archived with ``tar`` + gzip.
* Pruning removes the oldest ``success`` records (and their archive files) for
  a given ``backup_type`` when the total exceeds ``settings.backup_retention_count``.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.config import Settings
from makervault.models.backup_record import BackupRecord


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_backup_dir(backup_path: str) -> Path:
    """Create the backup directory if it does not exist and return it as a Path."""
    path = Path(backup_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _archive_name(backup_type: str, timestamp: datetime) -> str:
    ts = timestamp.strftime("%Y%m%dT%H%M%SZ")
    return f"makervault_{backup_type}_{ts}"


def _parse_db_url(database_url: str) -> dict[str, str]:
    """Extract connection components from a SQLAlchemy-style database URL.

    Handles ``postgresql+asyncpg://`` and plain ``postgresql://`` schemes.
    """
    # Normalise asyncpg driver prefix so urlparse works correctly
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": (parsed.path or "/makervault").lstrip("/"),
        "user": parsed.username or "makervault",
        "password": parsed.password or "",
    }


# ---------------------------------------------------------------------------
# Database backup
# ---------------------------------------------------------------------------


def run_db_backup(backup_path: str, database_url: str) -> tuple[str, int]:
    """Run ``pg_dump`` and return ``(file_path, file_size_bytes)``.

    Raises ``RuntimeError`` on failure with the captured stderr.
    """
    backup_dir = _ensure_backup_dir(backup_path)
    started_at = _utcnow()
    name = _archive_name("db", started_at)
    output_file = backup_dir / f"{name}.dump"

    conn = _parse_db_url(database_url)
    env = os.environ.copy()
    if conn["password"]:
        env["PGPASSWORD"] = conn["password"]

    cmd = [
        "pg_dump",
        "-h", conn["host"],
        "-p", conn["port"],
        "-U", conn["user"],
        "-d", conn["dbname"],
        "-Fc",                    # custom format
        "-f", str(output_file),
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pg_dump exited with non-zero status")

    size = output_file.stat().st_size
    return str(output_file), size


# ---------------------------------------------------------------------------
# Documents backup
# ---------------------------------------------------------------------------


def run_documents_backup(backup_path: str, document_store_path: str) -> tuple[str, int]:
    """Create a gzip-compressed tar archive of the document store.

    Returns ``(file_path, file_size_bytes)``.
    Raises ``RuntimeError`` on failure.
    """
    backup_dir = _ensure_backup_dir(backup_path)
    source_dir = Path(document_store_path)

    if not source_dir.exists():
        raise RuntimeError(
            f"Document store path does not exist: {document_store_path}"
        )

    started_at = _utcnow()
    name = _archive_name("documents", started_at)
    output_file = backup_dir / f"{name}.tar.gz"

    with tarfile.open(str(output_file), "w:gz") as tar:
        tar.add(str(source_dir), arcname="documents")

    size = output_file.stat().st_size
    return str(output_file), size


# ---------------------------------------------------------------------------
# Full backup (DB + documents)
# ---------------------------------------------------------------------------


def run_full_backup(
    backup_path: str, database_url: str, document_store_path: str
) -> tuple[str, int]:
    """Run both a DB dump and a documents archive and combine them into one
    tar archive.

    Returns ``(file_path, file_size_bytes)``.
    Raises ``RuntimeError`` on the first failure.
    """
    backup_dir = _ensure_backup_dir(backup_path)
    started_at = _utcnow()
    name = _archive_name("full", started_at)
    output_file = backup_dir / f"{name}.tar.gz"

    # Temporary directory inside the backup dir
    staging_dir = backup_dir / f".staging_{name}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- DB dump into staging ---
        conn = _parse_db_url(database_url)
        db_file = staging_dir / "database.dump"
        env = os.environ.copy()
        if conn["password"]:
            env["PGPASSWORD"] = conn["password"]

        cmd = [
            "pg_dump",
            "-h", conn["host"],
            "-p", conn["port"],
            "-U", conn["user"],
            "-d", conn["dbname"],
            "-Fc",
            "-f", str(db_file),
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)  # noqa: S603
        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip() or "pg_dump exited with non-zero status"
            )

        # --- Documents into staging ---
        source_dir = Path(document_store_path)
        if not source_dir.exists():
            raise RuntimeError(
                f"Document store path does not exist: {document_store_path}"
            )

        with tarfile.open(str(output_file), "w:gz") as tar:
            tar.add(str(db_file), arcname="database.dump")
            tar.add(str(source_dir), arcname="documents")

    finally:
        # Clean up staging directory
        import shutil
        shutil.rmtree(str(staging_dir), ignore_errors=True)

    size = output_file.stat().st_size
    return str(output_file), size


# ---------------------------------------------------------------------------
# Orchestrator — create record, run backup, update record
# ---------------------------------------------------------------------------


async def execute_backup(
    db: AsyncSession,
    settings: Settings,
    backup_type: str,
    triggered_by: str = "manual",
) -> BackupRecord:
    """Create a BackupRecord, run the appropriate backup, and update the record.

    Returns the updated BackupRecord.  The caller is responsible for committing
    the session.
    """
    record = BackupRecord(
        id=uuid.uuid4(),
        backup_type=backup_type,
        status="running",
        started_at=_utcnow(),
        triggered_by=triggered_by,
    )
    db.add(record)
    await db.flush()

    try:
        if backup_type == "db":
            file_path, file_size = run_db_backup(
                settings.backup_path, settings.database_url
            )
        elif backup_type == "documents":
            file_path, file_size = run_documents_backup(
                settings.backup_path, settings.document_store_path
            )
        else:  # "full"
            file_path, file_size = run_full_backup(
                settings.backup_path, settings.database_url, settings.document_store_path
            )

        record.status = "success"
        record.finished_at = _utcnow()
        record.file_path = file_path
        record.file_size_bytes = file_size

    except Exception as exc:  # noqa: BLE001
        record.status = "failed"
        record.finished_at = _utcnow()
        record.error_message = str(exc)

    await db.flush()
    return record


# ---------------------------------------------------------------------------
# Prune
# ---------------------------------------------------------------------------


async def prune_backups(
    db: AsyncSession,
    settings: Settings,
    backup_type: str | None = None,
) -> tuple[int, int, int]:
    """Delete old backup archives and their database records.

    If ``backup_type`` is given, only records of that type are pruned; otherwise
    all types are pruned independently.

    Returns ``(deleted_count, kept_count, freed_bytes)``.

    Only ``success`` records are considered for pruning — ``running`` and
    ``failed`` records are retained for visibility.
    """
    retention = settings.backup_retention_count
    if retention <= 0:
        # Pruning disabled — nothing to do
        return 0, 0, 0

    types_to_prune = [backup_type] if backup_type else ["db", "documents", "full"]

    total_deleted = 0
    total_kept = 0
    total_freed = 0

    for btype in types_to_prune:
        result = await db.execute(
            select(BackupRecord)
            .where(
                BackupRecord.backup_type == btype,
                BackupRecord.status == "success",
            )
            .order_by(BackupRecord.started_at.desc())
        )
        records: list[BackupRecord] = result.scalars().all()

        keep = records[:retention]
        delete = records[retention:]

        total_kept += len(keep)

        for rec in delete:
            # Remove the archive file if it still exists
            if rec.file_path:
                try:
                    Path(rec.file_path).unlink(missing_ok=True)
                    total_freed += rec.file_size_bytes or 0
                except OSError:
                    pass  # best-effort file removal
            await db.delete(rec)
            total_deleted += 1

    await db.flush()
    return total_deleted, total_kept, total_freed
