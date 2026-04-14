"""Add usage_history table.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-13
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------

USAGE_ACTION_TYPE_ENUM = postgresql.ENUM(
    "allocated",
    "used",
    "returned",
    "consumed",
    "tested",
    "damaged",
    name="usage_action_type_enum",
    create_type=False,  # managed explicitly in upgrade/downgrade
)


def upgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE usage_action_type_enum AS ENUM (
                'allocated', 'used', 'returned', 'consumed', 'tested', 'damaged'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))

    op.create_table(
        "usage_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "stock_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stock_items.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "part_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("parts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "action_type",
            USAGE_ACTION_TYPE_ENUM,
            nullable=False,
        ),
        sa.Column("quantity_delta", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
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
    op.drop_table("usage_history")
    USAGE_ACTION_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
