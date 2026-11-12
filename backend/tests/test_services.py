# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-29
"""Service-layer behavior: domain errors, receipt import reports, shopping list estimates."""
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import ItemUpdate, ParsedLine, ReceiptConfirmRequest, ShoppingListItemAdd
from app.models.models import Receipt, ShoppingListItem
from app.services.errors import ConflictError, NotFoundError
from app.services.item_service import ItemService
from app.services.receipt_service import ReceiptService
from app.services.shopping_list_service import ShoppingListService


def _request(shopping_date: date, *lines: ParsedLine, barcode: str | None = None) -> ReceiptConfirmRequest:
    return ReceiptConfirmRequest(shopping_date=shopping_date, barcode=barcode, lines=list(lines))


def _line(code: str, price: str, *, is_coupon: bool = False, coupon_for: str | None = None) -> ParsedLine:
    return ParsedLine(
        item_code=code,
        description=f"ITEM {code}",
        price=Decimal(price),
        is_coupon=is_coupon,
        coupon_for_code=coupon_for,
    )


async def _count(db: AsyncSession, model: type) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_confirm_report_matches_stored_report(db: AsyncSession) -> None:
    receipts = ReceiptService(db)
    await receipts.confirm(_request(date(2026, 1, 1), _line("100", "5.00"), _line("200", "2.00")))

    report = await receipts.confirm(
        _request(
            date(2026, 2, 1),
            _line("100", "6.00"),
            _line("200", "2.00"),
            _line("300", "9.00"),
            _line("900", "-1.00", is_coupon=True, coupon_for="100"),
        )
    )

    assert report == await receipts.import_report(report.receipt_id)
    assert [c.item_code for c in report.price_changes] == ["100"]
    assert [i.item_code for i in report.unchanged] == ["200"]
    assert [i.item_code for i in report.new_items] == ["300"]
    assert [(c.item_code, c.friendly_name) for c in report.coupons] == [("900", "Coupon for ITEM 100")]


async def test_confirm_rejects_duplicate_barcode_without_saving(db: AsyncSession) -> None:
    receipts = ReceiptService(db)
    await receipts.confirm(_request(date(2026, 1, 1), _line("100", "5.00"), barcode="B1"))

    with pytest.raises(ConflictError, match="B1 was already imported"):
        await receipts.confirm(_request(date(2026, 1, 2), _line("100", "5.00"), barcode="B1"))

    assert await _count(db, Receipt) == 1


async def test_get_receipt_lists_lines_in_receipt_order(db: AsyncSession) -> None:
    receipts = ReceiptService(db)
    report = await receipts.confirm(_request(date(2026, 1, 1), _line("200", "2.00"), _line("100", "1.00")))

    detail = await receipts.get_receipt(report.receipt_id)

    assert [line.item_code for line in detail.lines] == ["200", "100"]
    assert detail.line_count == 2
    assert [r.line_count for r in await receipts.list_receipts()] == [2]


@pytest.mark.parametrize(
    "call",
    [
        lambda db: ItemService(db).get_item(999),
        lambda db: ReceiptService(db).get_receipt(999),
        lambda db: ReceiptService(db).import_report(999),
        lambda db: ShoppingListService(db).get_list(999),
        lambda db: ShoppingListService(db).remove_entry(999, 1),
    ],
)
async def test_missing_records_raise_not_found(
    db: AsyncSession, call: Callable[[AsyncSession], Awaitable[object]]
) -> None:
    with pytest.raises(NotFoundError):
        await call(db)


async def test_shopping_list_estimates_and_cascade_delete(db: AsyncSession) -> None:
    report = await ReceiptService(db).confirm(
        _request(date(2026, 1, 1), _line("100", "2.50"), _line("200", "4.00"))
    )
    item_ids = {i.item_code: i.item_id for i in report.new_items}
    await ItemService(db).update_item(item_ids["200"], ItemUpdate(is_by_weight=True))
    lists = ShoppingListService(db)

    sl = await lists.create_list("   ")
    await lists.add_entry(sl.id, ShoppingListItemAdd(item_id=item_ids["100"], quantity=Decimal("3")))
    await lists.add_entry(sl.id, ShoppingListItemAdd(item_id=item_ids["200"]))
    full = await lists.get_list(sl.id)

    assert sl.name == "My List"
    # A by-weight item has no estimate until a $/lb is recorded, so only 3 × 2.50 counts.
    assert [e.estimated_cost for e in full.items] == [Decimal("7.50"), None]
    assert full.total_estimate == Decimal("7.50")

    await lists.delete_list(sl.id)

    assert await _count(db, ShoppingListItem) == 0


async def test_add_entry_rejects_missing_list_and_item(db: AsyncSession) -> None:
    lists = ShoppingListService(db)
    sl = await lists.create_list("L")

    with pytest.raises(NotFoundError, match="Shopping list not found"):
        await lists.add_entry(999, ShoppingListItemAdd(item_id=1))
    with pytest.raises(NotFoundError, match="Item not found"):
        await lists.add_entry(sl.id, ShoppingListItemAdd(item_id=999))
