# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-29
"""Items and their price history."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import ItemCreate, ItemDetailOut, ItemOut, ItemUpdate, PriceHistoryOut, PriceHistoryUpdate
from app.models.models import Item, PriceHistory, Receipt
from app.services.errors import ConflictError, NotFoundError
from app.services.pricing import LatestPurchase, latest_purchase_entry, latest_purchases


def _item_out(item: Item, latest: LatestPurchase | None) -> ItemOut:
    return ItemOut(
        id=item.id,
        item_code=item.item_code,
        description=item.description,
        friendly_name=item.friendly_name,
        tax_type=item.tax_type,
        is_by_weight=item.is_by_weight,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_price=latest.price if latest else None,
        last_purchased=latest.shopping_date if latest else None,
    )


def _history_out(ph: PriceHistory, shopping_date: date | None) -> PriceHistoryOut:
    return PriceHistoryOut(
        id=ph.id,
        receipt_id=ph.receipt_id,
        price=ph.price,
        price_per_lb=ph.price_per_lb,
        is_coupon=ph.is_coupon,
        coupon_for_item_id=ph.coupon_for_item_id,
        created_at=ph.created_at,
        shopping_date=shopping_date,
    )


class ItemService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_items(self) -> list[ItemOut]:
        items = (
            await self._db.execute(select(Item).order_by(func.coalesce(Item.friendly_name, Item.description)))
        ).scalars().all()
        latest = await latest_purchases(self._db)
        return [_item_out(item, latest.get(item.id)) for item in items]

    # ai: gpt-5 | 2026-11-03
    async def create_item(self, create: ItemCreate) -> ItemOut:
        item = Item(
            item_code=create.item_code.strip(),
            description=create.description.strip(),
            friendly_name=create.friendly_name.strip() if create.friendly_name else None,
            tax_type=create.tax_type.strip() if create.tax_type else None,
            is_by_weight=create.is_by_weight,
        )
        self._db.add(item)
        try:
            await self._db.commit()
        except IntegrityError as exc:
            await self._db.rollback()
            raise ConflictError(f"Item code {item.item_code} already exists") from exc
        await self._db.refresh(item)
        return _item_out(item, None)

    async def get_item(self, item_id: int) -> ItemDetailOut:
        item = await self._require_item(item_id)
        history_rows = (
            await self._db.execute(
                select(PriceHistory, Receipt.shopping_date)
                .join(Receipt, PriceHistory.receipt_id == Receipt.id)
                .where(PriceHistory.item_id == item_id)
                .order_by(Receipt.shopping_date.asc(), Receipt.id.asc(), PriceHistory.id.asc())
            )
        ).all()
        # The last history row can be a coupon, so "latest" comes from pricing, not from it.
        item_out = await self._item_out_with_price(item)
        return ItemDetailOut(
            **item_out.model_dump(),
            price_history=[_history_out(ph, shopping_date) for ph, shopping_date in history_rows],
        )

    async def update_item(self, item_id: int, update: ItemUpdate) -> ItemOut:
        item = await self._require_item(item_id)
        latest_entry = None
        # ai: gpt-5 | 2026-11-03
        if update.latest_price is not None:
            latest_entry = await latest_purchase_entry(self._db, item_id)
        if update.friendly_name is not None:
            item.friendly_name = update.friendly_name
        if update.tax_type is not None:
            item.tax_type = update.tax_type
        if update.is_by_weight is not None:
            item.is_by_weight = update.is_by_weight
        if latest_entry is not None:
            latest_entry.price = update.latest_price
        elif update.latest_price is not None:
            item.manual_price = update.latest_price
        await self._db.commit()
        await self._db.refresh(item)
        return await self._item_out_with_price(item)

    async def update_price_history_entry(self, entry_id: int, update: PriceHistoryUpdate) -> PriceHistoryOut:
        """Set or clear price_per_lb on a price history entry (for by-weight items)."""
        row = (
            await self._db.execute(
                select(PriceHistory, Receipt.shopping_date)
                .join(Receipt, PriceHistory.receipt_id == Receipt.id)
                .where(PriceHistory.id == entry_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Price history entry not found")
        ph, shopping_date = row
        ph.price_per_lb = update.price_per_lb
        await self._db.commit()
        await self._db.refresh(ph)
        return _history_out(ph, shopping_date)

    async def _require_item(self, item_id: int) -> Item:
        item = await self._db.get(Item, item_id)
        if item is None:
            raise NotFoundError("Item not found")
        return item

    async def _item_out_with_price(self, item: Item) -> ItemOut:
        return _item_out(item, (await latest_purchases(self._db, [item.id])).get(item.id))
