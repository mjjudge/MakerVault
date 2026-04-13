"""Documents, PartDocument, StockItemDocument, Project, ProjectDocument.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Enum types
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE document_type_enum AS ENUM (
                'datasheet','manual','pinout','schematic','vendor_page',
                'receipt','photo','project_note','setup_note','firmware_note','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE document_source_type_enum AS ENUM (
                'uploaded','captured_from_web','manual_note','generated_summary'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE part_document_relationship_enum AS ENUM (
                'primary_datasheet','manual','pinout','schematic',
                'supporting_reference','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE project_document_relationship_enum AS ENUM (
                'wiring_note','photo','setup_instruction','design_sketch',
                'ai_plan','reference','other'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # documents
    # ------------------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column(
            "document_type",
            postgresql.ENUM(
                "datasheet", "manual", "pinout", "schematic", "vendor_page",
                "receipt", "photo", "project_note", "setup_note", "firmware_note", "other",
                name="document_type_enum", create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "uploaded", "captured_from_web", "manual_note", "generated_summary",
                name="document_source_type_enum", create_type=False,
            ),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("local_path", sa.Text, nullable=True),
        sa.Column("mime_type", sa.Text, nullable=True),
        sa.Column("checksum", sa.Text, nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("text_extracted", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("version_label", sa.Text, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
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
    op.create_index("ix_documents_checksum", "documents", ["checksum"])

    # ------------------------------------------------------------------
    # projects (minimal stub; expanded in Epic 7)
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
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

    # ------------------------------------------------------------------
    # part_documents
    # ------------------------------------------------------------------
    op.create_table(
        "part_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "relationship_type",
            postgresql.ENUM(
                "primary_datasheet", "manual", "pinout", "schematic",
                "supporting_reference", "other",
                name="part_document_relationship_enum", create_type=False,
            ),
            nullable=False,
            server_default="other",
        ),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_part_documents_part_id", "part_documents", ["part_id"])
    op.create_index("ix_part_documents_document_id", "part_documents", ["document_id"])

    # ------------------------------------------------------------------
    # stock_item_documents
    # ------------------------------------------------------------------
    op.create_table(
        "stock_item_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("stock_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_stock_item_documents_stock_item_id", "stock_item_documents", ["stock_item_id"]
    )
    op.create_index(
        "ix_stock_item_documents_document_id", "stock_item_documents", ["document_id"]
    )

    # ------------------------------------------------------------------
    # project_documents
    # ------------------------------------------------------------------
    op.create_table(
        "project_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "relationship_type",
            postgresql.ENUM(
                "wiring_note", "photo", "setup_instruction", "design_sketch",
                "ai_plan", "reference", "other",
                name="project_document_relationship_enum", create_type=False,
            ),
            nullable=False,
            server_default="other",
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_project_documents_project_id", "project_documents", ["project_id"]
    )
    op.create_index(
        "ix_project_documents_document_id", "project_documents", ["document_id"]
    )


def downgrade() -> None:
    op.drop_table("project_documents")
    op.drop_table("stock_item_documents")
    op.drop_table("part_documents")
    op.drop_table("projects")
    op.drop_table("documents")

    op.execute("DROP TYPE IF EXISTS project_document_relationship_enum")
    op.execute("DROP TYPE IF EXISTS part_document_relationship_enum")
    op.execute("DROP TYPE IF EXISTS document_source_type_enum")
    op.execute("DROP TYPE IF EXISTS document_type_enum")
