"""Pydantic schemas for the hygiene dashboard (Epic 15)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class HygienePartSummary(BaseModel):
    """Minimal part representation used in hygiene lists."""

    id: uuid.UUID
    part_code: str
    name: str
    status: str

    model_config = {"from_attributes": True}


class SplitStockPart(BaseModel):
    """A part whose stock is spread across more than one location / container."""

    id: uuid.UUID
    part_code: str
    name: str
    status: str
    location_count: int
    locations: list[str]


class DuplicateGroup(BaseModel):
    """A group of parts that appear to be duplicates of each other."""

    reason: str
    parts: list[dict[str, Any]]


class HygieneDashboard(BaseModel):
    """Aggregated hygiene insights for the inventory."""

    parts_missing_documents: list[HygienePartSummary]
    parts_missing_aliases: list[HygienePartSummary]
    parts_missing_capabilities: list[HygienePartSummary]
    split_stock_parts: list[SplitStockPart]
    duplicate_groups: list[DuplicateGroup]


class MergeRequest(BaseModel):
    """Request body for merging a source part into a target (canonical) part."""

    target_part_id: uuid.UUID


class MergeResponse(BaseModel):
    """Response after a successful part merge."""

    target_part_id: uuid.UUID
    source_part_id: uuid.UUID
    stock_items_moved: int
    document_links_moved: int
    aliases_moved: int
    project_parts_moved: int
    source_archived: bool
