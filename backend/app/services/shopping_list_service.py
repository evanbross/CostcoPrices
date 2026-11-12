# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-29
"""Shopping lists, their entries, and cost estimates from latest prices."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.schemas import (
    ShoppingListItemAdd,
    ShoppingListItemOut,
    ShoppingListItemUpdate,
    ShoppingListOut,
    ShoppingListSummary,
)
from app.models.models import Item, ShoppingList, ShoppingListItem
from app.services.errors import NotFoundError
from app.services.pricing import LatestPurchase, latest_purchases

_DEFAULT_LIST_NAME = "My List"
_CENTS = Decimal("0.01")

# An async session can't lazy-load relationships, so everything that walks
# list.items or entry.item loads them up front.
_LIST_WITH_ITEMS = selectinload(ShoppingList.items).selectinload(ShoppingListItem.item)


def _estimated_cost(
    quantity: Decimal,
    is_by_weight: bool,
    latest_price: Decimal | None,
    latest_price_per_lb: Decimal | None,
) -> Decimal | None:
    if is_by_weight:
        if latest_price_per_lb is not None:
            return (quantity * latest_price_per_lb).quantize(_CENTS)
        return None  # can't estimate without $/lb
    if latest_price is not None:
        return (quantity * latest_price).quantize(_CENTS)
    return None


def _entry_out(sli: ShoppingListItem, latest: LatestPurchase | None) -> ShoppingListItemOut:
    item = sli.item
    latest_price = latest.price if latest else None
    latest_price_per_lb = latest.price_per_lb if latest else None
    return ShoppingListItemOut(
        id=sli.id,
        item_id=item.id,
        item_code=item.item_code,
        description=item.description,
        friendly_name=item.friendly_name,
        is_by_weight=item.is_by_weight,
        quantity=sli.quantity,
        note=sli.note,
        latest_price=latest_price,
        latest_price_per_lb=latest_price_per_lb,
        estimated_cost=_estimated_cost(sli.quantity, item.is_by_weight, latest_price, latest_price_per_lb),
    )


def _total_estimate(entries: list[ShoppingListItemOut]) -> Decimal | None:
    costs = [e.estimated_cost for e in entries if e.estimated_cost is not None]
    return sum(costs, Decimal("0")).quantize(_CENTS) if costs else None


class ShoppingListService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_summaries(self) -> list[ShoppingListSummary]:
        lists = (
            await self._db.execute(
                select(ShoppingList).options(_LIST_WITH_ITEMS).order_by(ShoppingList.updated_at.desc())
            )
        ).scalars().all()
        # One price query covering every list, not one per list.
        latest = await latest_purchases(self._db, list({sli.item_id for sl in lists for sli in sl.items}))

        summaries = []
        for sl in lists:
            entries = [_entry_out(sli, latest.get(sli.item_id)) for sli in sl.items]
            summaries.append(
                ShoppingListSummary(
                    id=sl.id,
                    name=sl.name,
                    created_at=sl.created_at,
                    updated_at=sl.updated_at,
                    item_count=len(sl.items),
                    total_estimate=_total_estimate(entries),
                )
            )
        return summaries

    async def get_list(self, list_id: int) -> ShoppingListOut:
        return await self._list_out(await self._require_list(list_id))

    async def create_list(self, name: str) -> ShoppingListOut:
        sl = ShoppingList(name=name.strip() or _DEFAULT_LIST_NAME)
        self._db.add(sl)
        await self._db.commit()
        return await self.get_list(sl.id)

    async def rename_list(self, list_id: int, name: str) -> ShoppingListOut:
        sl = await self._require_list(list_id)
        sl.name = name.strip() or sl.name
        await self._db.commit()
        return await self.get_list(list_id)

    async def delete_list(self, list_id: int) -> None:
        # Entries are loaded by _require_list so the delete-orphan cascade doesn't lazy-load.
        await self._db.delete(await self._require_list(list_id))
        await self._db.commit()

    async def add_entry(self, list_id: int, add: ShoppingListItemAdd) -> ShoppingListItemOut:
        if await self._db.get(ShoppingList, list_id) is None:
            raise NotFoundError("Shopping list not found")
        if await self._db.get(Item, add.item_id) is None:
            raise NotFoundError("Item not found")
        sli = ShoppingListItem(list_id=list_id, item_id=add.item_id, quantity=add.quantity, note=add.note)
        self._db.add(sli)
        await self._db.commit()
        return await self._entry_out_with_price(await self._require_entry(list_id, sli.id))

    async def update_entry(self, list_id: int, entry_id: int, update: ShoppingListItemUpdate) -> ShoppingListItemOut:
        sli = await self._require_entry(list_id, entry_id)
        if update.quantity is not None:
            sli.quantity = update.quantity
        if update.note is not None:
            sli.note = update.note or None
        await self._db.commit()
        return await self._entry_out_with_price(await self._require_entry(list_id, entry_id))

    async def remove_entry(self, list_id: int, entry_id: int) -> None:
        await self._db.delete(await self._require_entry(list_id, entry_id))
        await self._db.commit()

    async def _require_list(self, list_id: int) -> ShoppingList:
        """Load a list with its entries and their items.

        populate_existing makes a re-fetch after commit return fresh values (e.g. the
        bumped updated_at) rather than the identity map's cached copy.
        """
        sl = (
            await self._db.execute(
                select(ShoppingList)
                .where(ShoppingList.id == list_id)
                .options(_LIST_WITH_ITEMS)
                .execution_options(populate_existing=True)
            )
        ).scalars().first()
        if sl is None:
            raise NotFoundError("Shopping list not found")
        return sl

    async def _require_entry(self, list_id: int, entry_id: int) -> ShoppingListItem:
        sli = (
            await self._db.execute(
                select(ShoppingListItem)
                .where(ShoppingListItem.id == entry_id, ShoppingListItem.list_id == list_id)
                .options(selectinload(ShoppingListItem.item))
                .execution_options(populate_existing=True)
            )
        ).scalars().first()
        if sli is None:
            raise NotFoundError("List item not found")
        return sli

    async def _list_out(self, sl: ShoppingList) -> ShoppingListOut:
        latest = await latest_purchases(self._db, [sli.item_id for sli in sl.items])
        entries = [_entry_out(sli, latest.get(sli.item_id)) for sli in sl.items]
        return ShoppingListOut(
            id=sl.id,
            name=sl.name,
            created_at=sl.created_at,
            updated_at=sl.updated_at,
            items=entries,
            total_estimate=_total_estimate(entries),
        )

    async def _entry_out_with_price(self, sli: ShoppingListItem) -> ShoppingListItemOut:
        return _entry_out(sli, (await latest_purchases(self._db, [sli.item_id])).get(sli.item_id))
