"""Add project_parts table for BOM support (Epic 7).

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # project_parts  (Bill of Materials entries)
    # ------------------------------------------------------------------
    op.create_table(
        "project_parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quantity_required",
            sa.Numeric(12, 4),
            nullable=False,
            server_default="1",
        ),
        sa.Column("unit", sa.Text, nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_project_parts_project_id", "project_parts", ["project_id"])
    op.create_index("ix_project_parts_part_id", "project_parts", ["part_id"])


def downgrade() -> None:
    op.drop_table("project_parts")
