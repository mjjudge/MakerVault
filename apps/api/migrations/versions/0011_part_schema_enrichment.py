"""Add taxonomy + electrical + functional enrichment columns to parts.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-19
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------

# Columns added as nullable TEXT / ARRAY / JSONB so existing rows keep working.
_NEW_TEXT_COLUMNS = [
    "category",       # SEN, MCU, PWR, CON, …
    "subcategory",    # IMU, USB, CHG, …
    "family",         # MPU6050, TP4056, …
    "form_factor",    # Breakout board, Module, Bare IC, …
    "voltage",        # 3.3V, 5V, 3.3–5V
    "logic_level",    # 3.3V, 5V tolerant
]

_NEW_ARRAY_COLUMNS = [
    "interface",            # ["I2C", "SPI"]
    "pins",                 # ["VCC", "GND", "SCL", "SDA"]
    "capabilities",         # ["Measures acceleration (3-axis)"]
    "use_cases",            # ["Tilt sensing", "Robot balance"]
    "protection_features",  # ["Overcharge", "Reverse polarity"]
    "special_flags",        # ["High current", "Needs heatsink"]
]

# key_specs stays as JSONB (structured key-value pairs)


def upgrade() -> None:
    # Add enrich_part to the enrichment job type enum
    op.execute(
        "ALTER TYPE enrichment_job_type_enum ADD VALUE IF NOT EXISTS 'enrich_part'"
    )

    # Plain TEXT columns
    for col in _NEW_TEXT_COLUMNS:
        op.add_column("parts", sa.Column(col, sa.Text, nullable=True))

    # ARRAY(TEXT) columns — PostgreSQL native; SQLite gets TEXT (JSON string)
    for col in _NEW_ARRAY_COLUMNS:
        op.add_column(
            "parts",
            sa.Column(
                col,
                postgresql.ARRAY(sa.Text),
                nullable=True,
            ),
        )

    # key_specs as JSONB
    op.add_column(
        "parts",
        sa.Column("key_specs", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    for col in _NEW_TEXT_COLUMNS + _NEW_ARRAY_COLUMNS + ["key_specs"]:
        op.drop_column("parts", col)
