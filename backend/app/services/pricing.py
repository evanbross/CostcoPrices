# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-28
"""Single definition of "an item's current price" and "its price before a receipt".

Purchases are ordered by when they happened — the receipt's shopping_date — not
by when the receipt was imported (PriceHistory.created_at). Importing an old
receipt after a newer one must not make its price the "latest". Receipt.id breaks
ties between receipts on the same day, and PriceHistory.id breaks ties between
lines on the same receipt, so the ordering is always deterministic.

Coupon lines are never prices: they're discounts applied to a purchase.

Leaf module (imports only models) so both routes and services can use it.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import PriceHistory, Receipt

_NEWEST_FIRST = (Receipt.shopping_date.desc(), Receipt.id.desc(), PriceHistory.id.desc())


@dataclass(frozen=True)
class LatestPurchase:
    price: Decimal
    price_per_lb: Decimal | None
    shopping_date: date


async def latest_purchases(db: AsyncSession, item_ids: list[int] | None = None) -> dict[int, LatestPurchase]:
    """Map item_id → its most recent non-coupon purchase.

    One query regardless of how many items: a window function ranks each item's
    purchases newest-first and keeps rank 1. Pass item_ids to restrict it; omit
    it for every item. Items never purchased are absent from the result.
    """
    ranked_stmt = (
        select(
            PriceHistory.item_id,
            PriceHistory.price,
            PriceHistory.price_per_lb,
            Receipt.shopping_date,
            func.row_number()
            .over(partition_by=PriceHistory.item_id, order_by=_NEWEST_FIRST)
            .label("rank"),
        )
        .join(Receipt, PriceHistory.receipt_id == Receipt.id)
        .where(PriceHistory.is_coupon.is_(False))
    )
    if item_ids is not None:
        ranked_stmt = ranked_stmt.where(PriceHistory.item_id.in_(item_ids))
    ranked = ranked_stmt.subquery()

    rows = (
        await db.execute(
            select(ranked.c.item_id, ranked.c.price, ranked.c.price_per_lb, ranked.c.shopping_date)
            .where(ranked.c.rank == 1)
        )
    ).all()
    return {
        item_id: LatestPurchase(price=price, price_per_lb=price_per_lb, shopping_date=shopping_date)
        for item_id, price, price_per_lb, shopping_date in rows
    }


async def price_before_receipt(db: AsyncSession, item_id: int, receipt: Receipt) -> Decimal | None:
    """The item's most recent non-coupon price on a purchase that precedes `receipt`.

    "Precedes" uses the same (shopping_date, receipt id) ordering as
    latest_purchases, so a price-change report for an old receipt compares
    against what the price was back then, not against a later purchase.
    """
    return (
        await db.execute(
            select(PriceHistory.price)
            .join(Receipt, PriceHistory.receipt_id == Receipt.id)
            .where(
                PriceHistory.item_id == item_id,
                PriceHistory.is_coupon.is_(False),
                or_(
                    Receipt.shopping_date < receipt.shopping_date,
                    and_(Receipt.shopping_date == receipt.shopping_date, Receipt.id < receipt.id),
                ),
            )
            .order_by(*_NEWEST_FIRST)
            .limit(1)
        )
    ).scalars().first()
