"""Add ai_provider_configs table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-13
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column(
            "provider_type",
            sa.Enum(
                "openai",
                "anthropic",
                "ollama",
                "openai_compatible",
                name="ai_provider_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("api_key_env_var", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
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
    op.drop_table("ai_provider_configs")
    op.execute("DROP TYPE IF EXISTS ai_provider_type_enum")
