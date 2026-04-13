"""EnrichmentJob ORM model.

An EnrichmentJob represents a single AI enrichment task applied to a part or
document.  Jobs are created on-demand and run synchronously within the API
request.  Results are stored with full provenance (which provider produced
them, what confidence score was returned) and must be explicitly applied
before they change any entity field.

Job lifecycle
-------------
pending  → running  → done      (result ready for review)
                    → failed    (AI call errored or parse failed)
done     → dismissed            (user rejected the result)
done     → done (applied_at set) (user accepted and applied the result)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from makervault.database import Base
from makervault.models.base import TimestampMixin, new_uuid

# ---------------------------------------------------------------------------
# Enumeration values
# ---------------------------------------------------------------------------

ENRICHMENT_JOB_TYPE_VALUES = (
    "summarise_document",
    "extract_metadata",
    "generate_aliases",
    "classify_part",
)

ENRICHMENT_ENTITY_TYPE_VALUES = (
    "part",
    "document",
)

ENRICHMENT_JOB_STATUS_VALUES = (
    "pending",
    "running",
    "done",
    "failed",
    "dismissed",
)


class EnrichmentJob(TimestampMixin, Base):
    """A single AI enrichment task for a part or document.

    The ``entity_id`` column stores the UUID of the target entity.  Because
    the target can be either a ``Part`` or a ``Document``, there is no
    database-level FK — ``entity_type`` identifies which table to look in.

    ``result_json`` stores the raw AI output as returned by the provider and
    parsed by the enrichment service.  Its schema varies by ``job_type``:

    * ``summarise_document``  → ``{summary, key_specs, part_numbers}``
    * ``extract_metadata``    → ``{manufacturer, part_number, package_type,
                                   capabilities, tags}``
    * ``generate_aliases``    → ``{aliases, confidence}``
    * ``classify_part``       → ``{part_kind, tags, confidence}``
    """

    __tablename__ = "enrichment_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )

    job_type: Mapped[str] = mapped_column(
        Enum(
            *ENRICHMENT_JOB_TYPE_VALUES,
            name="enrichment_job_type_enum",
            create_type=True,
        ),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        Enum(
            *ENRICHMENT_ENTITY_TYPE_VALUES,
            name="enrichment_entity_type_enum",
            create_type=True,
        ),
        nullable=False,
    )

    # UUID of the Part or Document this job targets.
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        Enum(
            *ENRICHMENT_JOB_STATUS_VALUES,
            name="enrichment_job_status_enum",
            create_type=True,
        ),
        nullable=False,
        default="pending",
    )

    # Which provider ran this job (nullable: SET NULL if provider is deleted).
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Denormalised provider name kept for display even if provider is later deleted.
    provider_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Parsed AI output (schema depends on job_type — see class docstring).
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 0–100 confidence score extracted from AI output (null if not returned).
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Human-readable error message when status == "failed".
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when the result has been applied to the target entity.
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<EnrichmentJob id={self.id} type={self.job_type!r} "
            f"entity={self.entity_type}:{self.entity_id} status={self.status!r}>"
        )
