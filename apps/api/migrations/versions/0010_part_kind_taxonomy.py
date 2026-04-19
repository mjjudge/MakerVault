"""Expand part_kind_enum with taxonomy-aligned kind values.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-19
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# ---------------------------------------------------------------------------
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------

# New values to add to the existing part_kind_enum
_NEW_KIND_VALUES = (
    "sensor",
    "actuator",
    "connector",
    "communication",
    "power",
    "driver",
    "display",
    "switch",
    "passive",
    "mechanical",
)


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE is irreversible without recreating the enum,
    # so we use IF NOT EXISTS to make the migration idempotent.
    for value in _NEW_KIND_VALUES:
        op.execute(f"ALTER TYPE part_kind_enum ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum without
    # recreating it. Downgrade is intentionally a no-op — the new values
    # simply become unused rather than causing data loss.
    pass
