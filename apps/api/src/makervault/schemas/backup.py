"""Pydantic schemas for the backup API (Epic 16)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class BackupRecordResponse(BaseModel):
    """Full representation of a BackupRecord row."""

    id: uuid.UUID
    backup_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    file_path: str | None
    file_size_bytes: int | None
    triggered_by: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BackupStatusResponse(BaseModel):
    """High-level backup health summary shown in the admin dashboard."""

    last_successful_db_backup: datetime | None
    last_successful_documents_backup: datetime | None
    last_successful_full_backup: datetime | None
    last_backup_status: str | None  # status of the most-recent record overall
    last_backup_type: str | None
    last_backup_error: str | None
    total_records: int


class BackupTriggerRequest(BaseModel):
    """Request body for triggering a manual backup."""

    backup_type: Literal["db", "documents", "full"] = "full"


class BackupTriggerResponse(BaseModel):
    """Immediate response after enqueueing / starting a backup."""

    record_id: uuid.UUID
    backup_type: str
    status: str
    message: str


class BackupPruneResponse(BaseModel):
    """Result of a prune operation."""

    deleted_count: int
    kept_count: int
    freed_bytes: int
    message: str
