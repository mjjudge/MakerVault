"""Pydantic schemas for StockItem."""

import uuid
from datetime import date, datetime

from pydantic import Field, model_validator

from makervault.models.stock_item import STOCK_CONDITION_VALUES, STOCK_STATUS_VALUES
from makervault.schemas.base import BaseSchema


class StockItemCreate(BaseSchema):
    part_id: uuid.UUID
    location_id: uuid.UUID | None = None
    container_id: uuid.UUID | None = None
    quantity: float = Field(default=1, gt=0)
    unit: str | None = None
    status: str = Field(
        default="available",
        pattern=f"^({'|'.join(STOCK_STATUS_VALUES)})$",
    )
    condition: str | None = Field(
        default=None,
        pattern=f"^({'|'.join(STOCK_CONDITION_VALUES)})$",
    )
    serial_number: str | None = None
    batch_code: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    purchase_currency: str | None = None
    supplier: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_single_placement(self) -> "StockItemCreate":
        if self.location_id is not None and self.container_id is not None:
            raise ValueError(
                "A stock item must be placed in exactly one location: "
                "provide either location_id or container_id, not both."
            )
        if self.location_id is None and self.container_id is None:
            raise ValueError(
                "A stock item must be placed in exactly one location: "
                "provide either location_id or container_id."
            )
        return self


class StockItemUpdate(BaseSchema):
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    status: str | None = Field(
        default=None,
        pattern=f"^({'|'.join(STOCK_STATUS_VALUES)})$",
    )
    condition: str | None = Field(
        default=None,
        pattern=f"^({'|'.join(STOCK_CONDITION_VALUES)})$",
    )
    location_id: uuid.UUID | None = None
    container_id: uuid.UUID | None = None
    serial_number: str | None = None
    batch_code: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    purchase_currency: str | None = None
    supplier: str | None = None
    notes: str | None = None
    is_reserved: bool | None = None


class StockItemResponse(BaseSchema):
    id: uuid.UUID
    part_id: uuid.UUID
    location_id: uuid.UUID | None
    container_id: uuid.UUID | None
    quantity: float
    unit: str | None
    status: str
    condition: str | None
    serial_number: str | None
    batch_code: str | None
    purchase_date: date | None
    purchase_price: float | None
    purchase_currency: str | None
    supplier: str | None
    notes: str | None
    is_reserved: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    location_name: str | None = None
    container_name: str | None = None


class StockItemListResponse(BaseSchema):
    items: list[StockItemResponse]
    total: int


class BulkMoveRequest(BaseSchema):
    """Move a set of stock items to a new location or container."""

    stock_item_ids: list[uuid.UUID] = Field(..., min_length=1)
    location_id: uuid.UUID | None = None
    container_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_single_destination(self) -> "BulkMoveRequest":
        if self.location_id is not None and self.container_id is not None:
            raise ValueError(
                "Provide exactly one destination: either location_id or container_id, not both."
            )
        if self.location_id is None and self.container_id is None:
            raise ValueError(
                "Provide exactly one destination: either location_id or container_id."
            )
        return self


class BulkMoveResponse(BaseSchema):
    moved: int
    not_found: list[str]
