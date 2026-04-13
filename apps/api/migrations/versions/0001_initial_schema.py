"""Initial schema: categories, locations, containers, parts, stock_items.

Revision ID: 0001
Revises:
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE part_kind_enum AS ENUM (
                'component','board','module','device','tool','consumable',
                'material','accessory','cable','power_supply','enclosure'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE part_status_enum AS ENUM ('active','draft','archived');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE part_provenance_enum AS ENUM ('manual','ai_enriched','imported');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE stock_status_enum AS ENUM (
                'available','reserved','consumed','missing','damaged','unknown'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE stock_condition_enum AS ENUM (
                'new','used','untested','faulty','for_parts'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # categories
    # ------------------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("parent_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=True),
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
            ["parent_category_id"],
            ["categories.id"],
            ondelete="SET NULL",
        ),
    )

    # ------------------------------------------------------------------
    # locations
    # ------------------------------------------------------------------
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("parent_location_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["parent_location_id"],
            ["locations.id"],
            ondelete="SET NULL",
        ),
    )

    # ------------------------------------------------------------------
    # containers
    # ------------------------------------------------------------------
    op.create_table(
        "containers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("label_code", sa.Text, nullable=True, unique=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_container_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["location_id"], ["locations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["parent_container_id"], ["containers.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN parent_container_id IS NOT NULL THEN 1 ELSE 0 END = 1",
            name="ck_container_single_parent",
        ),
    )
    op.create_index("ix_containers_label_code", "containers", ["label_code"])
    op.create_index("ix_containers_location_id", "containers", ["location_id"])
    op.create_index(
        "ix_containers_parent_container_id", "containers", ["parent_container_id"]
    )

    # ------------------------------------------------------------------
    # parts
    # ------------------------------------------------------------------
    op.create_table(
        "parts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("part_code", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("short_description", sa.Text, nullable=True),
        sa.Column("long_description", sa.Text, nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "part_kind",
            postgresql.ENUM(
                "component", "board", "module", "device", "tool", "consumable",
                "material", "accessory", "cable", "power_supply", "enclosure",
                name="part_kind_enum", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("manufacturer", sa.Text, nullable=True),
        sa.Column("manufacturer_part_number", sa.Text, nullable=True),
        sa.Column("default_unit", sa.Text, nullable=False, server_default="pcs"),
        sa.Column("package_type", sa.Text, nullable=True),
        sa.Column("spec_summary", sa.Text, nullable=True),
        sa.Column("capabilities_json", postgresql.JSONB, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("aliases", postgresql.ARRAY(sa.Text), nullable=True),
        sa.Column("search_text", postgresql.TSVECTOR, nullable=True),
        sa.Column("is_consumable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_serialised", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_hazardous", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "draft", "archived",
                name="part_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("identification_confidence", sa.Integer, nullable=True),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "provenance",
            postgresql.ENUM(
                "manual", "ai_enriched", "imported",
                name="part_provenance_enum", create_type=False,
            ),
            nullable=True,
            server_default="manual",
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
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_parts_part_code", "parts", ["part_code"])
    op.create_index("ix_parts_category_id", "parts", ["category_id"])
    op.create_index(
        "ix_parts_search_text", "parts", ["search_text"], postgresql_using="gin"
    )

    # ------------------------------------------------------------------
    # stock_items
    # ------------------------------------------------------------------
    op.create_table(
        "stock_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("unit", sa.Text, nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "available", "reserved", "consumed", "missing", "damaged", "unknown",
                name="stock_status_enum", create_type=False,
            ),
            nullable=False,
            server_default="available",
        ),
        sa.Column(
            "condition",
            postgresql.ENUM(
                "new", "used", "untested", "faulty", "for_parts",
                name="stock_condition_enum", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("serial_number", sa.Text, nullable=True),
        sa.Column("batch_code", sa.Text, nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("purchase_price", sa.Numeric(12, 4), nullable=True),
        sa.Column("purchase_currency", sa.Text, nullable=True),
        sa.Column("supplier", sa.Text, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_reserved", sa.Boolean, nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["location_id"], ["locations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["container_id"], ["containers.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "CASE WHEN location_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN container_id IS NOT NULL THEN 1 ELSE 0 END = 1",
            name="ck_stock_item_single_placement",
        ),
    )
    op.create_index("ix_stock_items_part_id", "stock_items", ["part_id"])
    op.create_index("ix_stock_items_location_id", "stock_items", ["location_id"])
    op.create_index("ix_stock_items_container_id", "stock_items", ["container_id"])


def downgrade() -> None:
    op.drop_table("stock_items")
    op.drop_table("parts")
    op.drop_table("containers")
    op.drop_table("locations")
    op.drop_table("categories")

    op.execute("DROP TYPE IF EXISTS stock_condition_enum")
    op.execute("DROP TYPE IF EXISTS stock_status_enum")
    op.execute("DROP TYPE IF EXISTS part_provenance_enum")
    op.execute("DROP TYPE IF EXISTS part_status_enum")
    op.execute("DROP TYPE IF EXISTS part_kind_enum")
