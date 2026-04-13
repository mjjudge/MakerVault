"""Add enrichment_jobs table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-13
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # Enum types (idempotent with DO $$ block)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE enrichment_job_type_enum AS ENUM (
                'summarise_document', 'extract_metadata',
                'generate_aliases', 'classify_part'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE enrichment_entity_type_enum AS ENUM (
                'part', 'document'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE enrichment_job_status_enum AS ENUM (
                'pending', 'running', 'done', 'failed', 'dismissed'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.create_table(
        "enrichment_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "job_type",
            postgresql.ENUM(
                "summarise_document",
                "extract_metadata",
                "generate_aliases",
                "classify_part",
                name="enrichment_job_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            postgresql.ENUM(
                "part",
                "document",
                name="enrichment_entity_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "running",
                "done",
                "failed",
                "dismissed",
                name="enrichment_job_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_name", sa.Text, nullable=True),
        sa.Column("result_json", postgresql.JSONB, nullable=True),
        sa.Column("confidence", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["ai_provider_configs.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_enrichment_jobs_entity_id", "enrichment_jobs", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_enrichment_jobs_entity_id", table_name="enrichment_jobs")
    op.drop_table("enrichment_jobs")
    op.execute("DROP TYPE IF EXISTS enrichment_job_type_enum")
    op.execute("DROP TYPE IF EXISTS enrichment_entity_type_enum")
    op.execute("DROP TYPE IF EXISTS enrichment_job_status_enum")
