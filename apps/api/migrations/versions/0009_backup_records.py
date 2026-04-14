"""Add backup_records table.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-14
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------

BACKUP_TYPE_ENUM = postgresql.ENUM(
    "db",
    "documents",
    "full",
    name="backup_type_enum",
)

BACKUP_STATUS_ENUM = postgresql.ENUM(
    "running",
    "success",
    "failed",
    name="backup_status_enum",
)


def upgrade() -> None:
    BACKUP_TYPE_ENUM.create(op.get_bind(), checkfirst=True)
    BACKUP_STATUS_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "backup_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "backup_type",
            BACKUP_TYPE_ENUM,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            BACKUP_STATUS_ENUM,
            nullable=False,
            server_default="running",
            index=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column(
            "triggered_by",
            sa.Text,
            nullable=False,
            server_default="manual",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("backup_records")
    BACKUP_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    BACKUP_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
