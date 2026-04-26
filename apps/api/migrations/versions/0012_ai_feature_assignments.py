"""Add ai_feature_assignments table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-24
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    op.create_table(
        "ai_feature_assignments",
        sa.Column("feature_key", sa.Text, primary_key=True),
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ai_feature_assignments_provider_id",
        "ai_feature_assignments",
        ["provider_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_feature_assignments_provider_id", "ai_feature_assignments")
    op.drop_table("ai_feature_assignments")
