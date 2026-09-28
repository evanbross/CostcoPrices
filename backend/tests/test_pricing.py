# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# LICENSE: Personal Use Only
# This source code is made available for personal, non-commercial use only.
# You may read, study, and run this code for personal purposes.
# You may NOT:
#   - Use this code, in whole or in part, in any commercial product or service
#   - Sell, sublicense, or otherwise monetize this code or derivatives of it
#   - Redistribute this code without explicit written permission from ZombieTech LLC
#
# No warranty is provided, express or implied. Use at your own risk.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-28
"""Prices follow the receipt's shopping_date, never the order receipts were imported."""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.schemas import ParsedLine
from app.models.models import Item, PriceHistory, Receipt
from app.services.pricing import latest_purchases, price_before_receipt
from app.services.receipt_service import confirm_receipt


def _item(db: Session, code: str) -> Item:
    item = Item(item_code=code, description=f"ITEM {code}")
    db.add(item)
    db.flush()
    return item


def _receipt(db: Session, shopping_date: date) -> Receipt:
    receipt = Receipt(shopping_date=shopping_date)
    db.add(receipt)
    db.flush()
    return receipt


def _buy(
    db: Session,
    item: Item,
    receipt: Receipt,
    price: str,
    *,
    is_coupon: bool = False,
    price_per_lb: str | None = None,
) -> None:
    db.add(
        PriceHistory(
            item_id=item.id,
            receipt_id=receipt.id,
            price=Decimal(price),
            is_coupon=is_coupon,
            price_per_lb=Decimal(price_per_lb) if price_per_lb else None,
        )
    )
    db.flush()


def _line(code: str, price: str) -> ParsedLine:
    return ParsedLine(item_code=code, description=f"ITEM {code}", price=Decimal(price))


def test_latest_uses_shopping_date_not_import_order(db: Session) -> None:
    item = _item(db, "100")
    _buy(db, item, _receipt(db, date(2026, 1, 6)), "4.59")
    _buy(db, item, _receipt(db, date(2025, 9, 1)), "5.99")  # older trip, imported later

    latest = latest_purchases(db)[item.id]

    assert latest.price == Decimal("4.59")
    assert latest.shopping_date == date(2026, 1, 6)


def test_latest_same_day_prefers_later_receipt(db: Session) -> None:
    item = _item(db, "100")
    day = date(2026, 3, 1)
    _buy(db, item, _receipt(db, day), "1.00")
    _buy(db, item, _receipt(db, day), "2.00")

    assert latest_purchases(db)[item.id].price == Decimal("2.00")


def test_latest_ignores_coupons(db: Session) -> None:
    item = _item(db, "100")
    receipt = _receipt(db, date(2026, 3, 1))
    _buy(db, item, receipt, "9.99")
    _buy(db, item, _receipt(db, date(2026, 4, 1)), "-3.00", is_coupon=True)

    latest = latest_purchases(db)[item.id]

    assert latest.price == Decimal("9.99")
    assert latest.shopping_date == date(2026, 3, 1)


def test_latest_carries_price_per_lb(db: Session) -> None:
    item = _item(db, "100")
    _buy(db, item, _receipt(db, date(2026, 3, 1)), "12.50", price_per_lb="4.9900")

    assert latest_purchases(db)[item.id].price_per_lb == Decimal("4.9900")


def test_latest_filters_by_item_ids_and_omits_unpurchased(db: Session) -> None:
    bought = _item(db, "100")
    other = _item(db, "200")
    never = _item(db, "300")
    receipt = _receipt(db, date(2026, 3, 1))
    _buy(db, bought, receipt, "1.00")
    _buy(db, other, receipt, "2.00")

    assert set(latest_purchases(db)) == {bought.id, other.id}
    assert set(latest_purchases(db, [bought.id, never.id])) == {bought.id}


def test_price_before_receipt_uses_earlier_trip(db: Session) -> None:
    item = _item(db, "100")
    _buy(db, item, _receipt(db, date(2025, 7, 1)), "3.00")
    _buy(db, item, _receipt(db, date(2026, 2, 1)), "5.00")
    middle = _receipt(db, date(2025, 10, 1))  # imported last, dated in between
    _buy(db, item, middle, "4.00")

    assert price_before_receipt(db, item.id, middle) == Decimal("3.00")


def test_price_before_receipt_none_for_earliest_trip(db: Session) -> None:
    item = _item(db, "100")
    _buy(db, item, _receipt(db, date(2026, 2, 1)), "5.00")
    earliest = _receipt(db, date(2025, 7, 1))
    _buy(db, item, earliest, "3.00")

    assert price_before_receipt(db, item.id, earliest) is None


def test_price_before_receipt_same_day_earlier_receipt_counts(db: Session) -> None:
    item = _item(db, "100")
    day = date(2026, 3, 1)
    _buy(db, item, _receipt(db, day), "1.00")
    second = _receipt(db, day)
    _buy(db, item, second, "2.00")

    assert price_before_receipt(db, item.id, second) == Decimal("1.00")


def test_price_before_receipt_skips_coupons(db: Session) -> None:
    item = _item(db, "100")
    first = _receipt(db, date(2026, 1, 1))
    _buy(db, item, first, "7.00")
    _buy(db, item, _receipt(db, date(2026, 2, 1)), "-2.00", is_coupon=True)
    later = _receipt(db, date(2026, 3, 1))

    assert price_before_receipt(db, item.id, later) == Decimal("7.00")


def test_confirm_old_receipt_compares_against_its_own_past(db: Session) -> None:
    confirm_receipt(db, date(2025, 7, 1), None, None, None, [_line("100", "3.00")])
    confirm_receipt(db, date(2026, 2, 1), None, None, None, [_line("100", "5.00")])

    report = confirm_receipt(db, date(2025, 10, 1), None, None, None, [_line("100", "4.00")])

    assert [c.old_price for c in report.price_changes] == [Decimal("3.00")]
    assert report.price_changes[0].change == Decimal("1.00")
    item_id = report.price_changes[0].item_id
    assert latest_purchases(db)[item_id].price == Decimal("5.00")


def test_confirm_receipt_older_than_all_history_reports_new(db: Session) -> None:
    confirm_receipt(db, date(2026, 2, 1), None, None, None, [_line("100", "5.00")])

    report = confirm_receipt(db, date(2025, 7, 1), None, None, None, [_line("100", "3.00")])

    assert [i.item_code for i in report.new_items] == ["100"]
    assert report.price_changes == []
    assert report.unchanged == []


def test_confirm_same_price_is_unchanged(db: Session) -> None:
    confirm_receipt(db, date(2026, 1, 1), None, None, None, [_line("100", "5.00")])

    report = confirm_receipt(db, date(2026, 2, 1), None, None, None, [_line("100", "5.00")])

    assert [i.item_code for i in report.unchanged] == ["100"]
