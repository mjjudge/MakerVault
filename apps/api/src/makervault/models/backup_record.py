"""BackupRecord ORM model.

A BackupRecord captures the outcome of a single backup run — either triggered
manually via the API or by a scheduled job.  Both database dumps and document
store archives are tracked independently so operators can see at a glance which
data was last backed up and when.

Lifecycle
---------
running  → success   (archive written, file_path and file_size_bytes set)
         → failed    (error_message populated)
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

# ---------------------------------------------------------------------------
# Enumeration values
# ---------------------------------------------------------------------------

BACKUP_TYPE_VALUES = (
    "db",          # PostgreSQL dump only
    "documents",   # Document store archive only
    "full",        # Both DB dump and documents archive
)

BACKUP_STATUS_VALUES = (
    "running",
    "success",
    "failed",
)


class BackupRecord(TimestampMixin, Base):
    """Metadata record for a single backup run.

    ``file_path`` is the absolute path (inside the container / host) of the
    backup archive.  It is set only when ``status == "success"``.

    ``file_size_bytes`` is the size of the resulting archive file in bytes,
    populated after a successful backup.

    ``triggered_by`` indicates how the backup was started:
    ``"manual"`` (API call) or ``"scheduled"`` (worker cron job).
    """

    __tablename__ = "backup_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    backup_type: Mapped[str] = mapped_column(
        Enum(*BACKUP_TYPE_VALUES, name="backup_type_enum", create_type=True),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        Enum(*BACKUP_STATUS_VALUES, name="backup_status_enum", create_type=True),
        nullable=False,
        default="running",
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Absolute path of the archive file (set on success).
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Archive size in bytes (set on success).
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # How the backup was initiated.
    triggered_by: Mapped[str] = mapped_column(
        Text, nullable=False, default="manual"
    )

    # Human-readable error message when status == "failed".
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BackupRecord id={self.id} type={self.backup_type!r} "
            f"status={self.status!r} started_at={self.started_at}>"
        )
