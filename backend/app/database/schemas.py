# ai: claude-sonnet-4-6 | 2026-06-18
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

class ItemBase(BaseModel):
    item_code: str
    description: str
    friendly_name: str | None = None
    tax_type: str | None = None
    is_by_weight: bool = False


class ItemUpdate(BaseModel):
    friendly_name: str | None = None
    tax_type: str | None = None
    is_by_weight: bool | None = None


class PriceHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_id: int
    price: Decimal
    price_per_lb: Decimal | None = None
    is_coupon: bool
    coupon_for_item_id: int | None
    created_at: datetime
    shopping_date: date | None = None


class PriceHistoryUpdate(BaseModel):
    price_per_lb: Decimal | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str
    description: str
    friendly_name: str | None
    tax_type: str | None
    is_by_weight: bool
    created_at: datetime
    updated_at: datetime
    latest_price: Decimal | None = None


class ItemDetailOut(ItemOut):
    price_history: list[PriceHistoryOut] = []


# ---------------------------------------------------------------------------
# Receipts / OCR
# ---------------------------------------------------------------------------

class ParsedLine(BaseModel):
    """One line from OCR — returned to the client for review before saving."""
    item_code: str
    description: str
    price: Decimal
    tax_type: str | None = None
    is_coupon: bool = False
    coupon_for_code: str | None = None
    line_prefix: str | None = None


class OcrResponse(BaseModel):
    lines: list[ParsedLine]
    raw_text: str | None = None
    barcode: str | None = None
    detected_date: str | None = None
    detected_store: str | None = None


class ReceiptConfirmRequest(BaseModel):
    shopping_date: date
    store_location: str | None = None
    notes: str | None = None
    barcode: str | None = None
    lines: list[ParsedLine]


class ReceiptLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_code: str
    description: str
    friendly_name: str | None
    price: Decimal
    is_coupon: bool
    coupon_for_item_id: int | None


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcode: str | None
    shopping_date: date
    store_location: str | None
    notes: str | None
    created_at: datetime
    line_count: int = 0


class ReceiptDetailOut(ReceiptOut):
    lines: list[ReceiptLineOut] = []


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class PriceChange(BaseModel):
    item_id: int
    item_code: str
    description: str
    friendly_name: str | None
    old_price: Decimal
    new_price: Decimal
    change: Decimal


class ImportReportItem(BaseModel):
    item_id: int
    item_code: str
    description: str
    friendly_name: str | None
    price: Decimal


class ImportReport(BaseModel):
    receipt_id: int
    new_items: list[ImportReportItem] = []
    price_changes: list[PriceChange] = []
    unchanged: list[ImportReportItem] = []
    coupons: list[ImportReportItem] = []


# ---------------------------------------------------------------------------
# Shopping Lists
# ---------------------------------------------------------------------------

class ShoppingListItemAdd(BaseModel):
    item_id: int
    quantity: Decimal = Decimal("1")
    note: str | None = None


class ShoppingListItemUpdate(BaseModel):
    quantity: Decimal | None = None
    note: str | None = None


class ShoppingListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_code: str
    description: str
    friendly_name: str | None
    is_by_weight: bool
    quantity: Decimal
    note: str | None
    latest_price: Decimal | None
    latest_price_per_lb: Decimal | None
    estimated_cost: Decimal | None


class ShoppingListCreate(BaseModel):
    name: str


class ShoppingListRename(BaseModel):
    name: str


class ShoppingListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[ShoppingListItemOut] = []
    total_estimate: Decimal | None


class ShoppingListSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    item_count: int
    total_estimate: Decimal | None


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
