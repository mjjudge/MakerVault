"""Backup API router (Epic 16).

Endpoints
---------
GET  /backup/status             — high-level backup health summary
GET  /backup/records            — paginated list of all backup records
POST /backup/trigger            — trigger a manual backup run
POST /backup/prune              — prune old backup archives
GET  /backup/restore-checklist  — download a plain-text restore guide
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.config import Settings, get_settings
from makervault.database import get_db_session
from makervault.models.backup_record import BackupRecord
from makervault.schemas.backup import (
    BackupPruneResponse,
    BackupRecordResponse,
    BackupStatusResponse,
    BackupTriggerRequest,
    BackupTriggerResponse,
)
from makervault.services.backup_service import execute_backup, prune_backups

router = APIRouter(tags=["backup"])

_RESTORE_CHECKLIST = """\
MakerVault — Restore Checklist
===============================

This checklist walks you through restoring MakerVault from a backup archive.
Keep a printed copy of this document in a safe location.

Prerequisites
-------------
1. A working Docker / Docker Compose installation.
2. Access to a recent backup archive (DB dump and/or documents archive).
3. The original .env file (or a reconstructed one with matching SECRET_KEY and
   POSTGRES_PASSWORD values).

Steps
-----

Step 1 — Stop the running stack (if any)
   docker compose -f infra/docker/docker-compose.yml down

Step 2 — Restore the PostgreSQL database
   a. Identify the .dump file from your most recent successful "db" or "full"
      backup.  The filename looks like:
        makervault_db_20260101T120000Z.dump
        makervault_full_20260101T120000Z.tar.gz  (extract database.dump first)

   b. Extract database.dump from a full archive if needed:
        tar -xzf makervault_full_TIMESTAMP.tar.gz database.dump

   c. Start only the db service:
        docker compose -f infra/docker/docker-compose.yml up -d db

   d. Wait for PostgreSQL to be healthy:
        docker compose -f infra/docker/docker-compose.yml ps

   e. Restore the dump into the database (replace <container> and <vars>):
        docker exec -i <db-container> pg_restore \\
          -U $POSTGRES_USER -d $POSTGRES_DB -Fc < database.dump

Step 3 — Restore the document store
   a. Identify the documents archive from your most recent successful
      "documents" or "full" backup.

   b. Extract the archive into the documents volume:
        docker run --rm \\
          -v makervault_documents:/data/makervault/documents \\
          -v /path/to/backup:/backup \\
          alpine tar -xzf /backup/makervault_documents_TIMESTAMP.tar.gz \\
          -C /data/makervault

      For a full archive, extract the documents directory:
        tar -xzf makervault_full_TIMESTAMP.tar.gz documents/

Step 4 — Start the full stack
   docker compose -f infra/docker/docker-compose.yml up -d

Step 5 — Verify
   a. Open the MakerVault UI and confirm parts/stock/documents are visible.
   b. Check the backup status endpoint:
        GET /api/backup/status
   c. Run a fresh backup to confirm the restored system is operational:
        POST /api/backup/trigger  {"backup_type": "full"}

Notes
-----
* The SECRET_KEY in your .env must match the one used when the data was
  originally captured.  A mismatched key will break session tokens.
* Never share your .env file or POSTGRES_PASSWORD in public channels.
* Test this procedure periodically to confirm backups are restorable.
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GET /backup/status
# ---------------------------------------------------------------------------


@router.get(
    "/backup/status",
    response_model=BackupStatusResponse,
    summary="Backup health summary",
)
async def backup_status(
    db: AsyncSession = Depends(get_db_session),
) -> BackupStatusResponse:
    """Return a high-level summary of backup health.

    Shows the timestamp of the last successful backup for each type (db,
    documents, full) plus the overall status of the most recent backup run.
    """

    async def _last_success(btype: str) -> datetime | None:
        result = await db.execute(
            select(BackupRecord.started_at)
            .where(
                BackupRecord.backup_type == btype,
                BackupRecord.status == "success",
            )
            .order_by(desc(BackupRecord.started_at))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row

    last_db = await _last_success("db")
    last_docs = await _last_success("documents")
    last_full = await _last_success("full")

    # Most-recent record overall
    latest_result = await db.execute(
        select(BackupRecord)
        .order_by(desc(BackupRecord.started_at))
        .limit(1)
    )
    latest: BackupRecord | None = latest_result.scalar_one_or_none()

    count_result = await db.execute(select(func.count()).select_from(BackupRecord))
    total = count_result.scalar_one()

    return BackupStatusResponse(
        last_successful_db_backup=last_db,
        last_successful_documents_backup=last_docs,
        last_successful_full_backup=last_full,
        last_backup_status=latest.status if latest else None,
        last_backup_type=latest.backup_type if latest else None,
        last_backup_error=latest.error_message if latest else None,
        total_records=total,
    )


# ---------------------------------------------------------------------------
# GET /backup/records
# ---------------------------------------------------------------------------


@router.get(
    "/backup/records",
    response_model=list[BackupRecordResponse],
    summary="List backup records",
)
async def list_backup_records(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[BackupRecordResponse]:
    """Return backup records ordered by most-recent first."""
    result = await db.execute(
        select(BackupRecord)
        .order_by(desc(BackupRecord.started_at))
        .limit(limit)
        .offset(offset)
    )
    records = result.scalars().all()
    return [BackupRecordResponse.model_validate(r) for r in records]


# ---------------------------------------------------------------------------
# POST /backup/trigger
# ---------------------------------------------------------------------------


@router.post(
    "/backup/trigger",
    response_model=BackupTriggerResponse,
    summary="Trigger a manual backup",
    status_code=202,
)
async def trigger_backup(
    body: BackupTriggerRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BackupTriggerResponse:
    """Trigger a backup run synchronously.

    The backup executes within the request and returns once complete (success
    or failure).  The resulting ``BackupRecord`` is committed to the database
    regardless of outcome so that failures are visible.

    For long-running environments a worker-based async approach is recommended;
    this endpoint is intentionally simple and suitable for a self-hosted
    single-node deployment.
    """
    record = await execute_backup(
        db=db,
        settings=settings,
        backup_type=body.backup_type,
        triggered_by="manual",
    )
    await db.commit()
    await db.refresh(record)

    if record.status == "success":
        msg = (
            f"{body.backup_type} backup completed successfully "
            f"({record.file_size_bytes or 0:,} bytes)."
        )
    else:
        msg = f"{body.backup_type} backup failed: {record.error_message}"

    return BackupTriggerResponse(
        record_id=record.id,
        backup_type=record.backup_type,
        status=record.status,
        message=msg,
    )


# ---------------------------------------------------------------------------
# POST /backup/prune
# ---------------------------------------------------------------------------


@router.post(
    "/backup/prune",
    response_model=BackupPruneResponse,
    summary="Prune old backup archives",
)
async def prune_old_backups(
    backup_type: str | None = Query(
        default=None,
        description=(
            "Type to prune (db | documents | full). "
            "Omit to prune all types."
        ),
    ),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> BackupPruneResponse:
    """Delete old backup archives that exceed the configured retention count.

    Only ``success`` records are pruned.  ``failed`` records are kept for
    visibility until explicitly deleted.

    The retention count is configured via ``BACKUP_RETENTION_COUNT`` (default
    10).  Set to ``0`` to disable pruning.
    """
    deleted, kept, freed = await prune_backups(
        db=db,
        settings=settings,
        backup_type=backup_type,
    )
    await db.commit()

    if settings.backup_retention_count <= 0:
        msg = "Pruning is disabled (BACKUP_RETENTION_COUNT=0)."
    elif deleted == 0:
        msg = f"No archives to prune. Keeping {kept} record(s)."
    else:
        freed_mb = freed / (1024 * 1024)
        msg = (
            f"Pruned {deleted} archive(s), freed {freed_mb:.1f} MB. "
            f"Kept {kept} record(s)."
        )

    return BackupPruneResponse(
        deleted_count=deleted,
        kept_count=kept,
        freed_bytes=freed,
        message=msg,
    )


# ---------------------------------------------------------------------------
# GET /backup/restore-checklist
# ---------------------------------------------------------------------------


@router.get(
    "/backup/restore-checklist",
    response_class=PlainTextResponse,
    summary="Download the restore checklist",
)
async def restore_checklist() -> PlainTextResponse:
    """Return a plain-text step-by-step restore guide.

    Suitable for printing or saving offline so it is available when the system
    is down and the UI is inaccessible.
    """
    return PlainTextResponse(
        content=_RESTORE_CHECKLIST,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="makervault-restore-checklist.txt"'
        },
    )
