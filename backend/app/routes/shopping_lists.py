# ai: claude-sonnet-4-6 | 2026-06-20
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.database import get_db
from app.database.schemas import (
    ShoppingListCreate,
    ShoppingListItemAdd,
    ShoppingListItemOut,
    ShoppingListItemUpdate,
    ShoppingListOut,
    ShoppingListRename,
    ShoppingListSummary,
)
from app.models.models import Item, ShoppingList, ShoppingListItem
from app.services.pricing import LatestPurchase, latest_purchases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/shopping-lists", tags=["shopping-lists"])

# ai: claude-opus-5-5 | 2026-09-28
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
            return (quantity * latest_price_per_lb).quantize(Decimal("0.01"))
        return None  # can't estimate without $/lb
    if latest_price is not None:
        return (quantity * latest_price).quantize(Decimal("0.01"))
    return None


# ai: claude-opus-5-5 | 2026-09-28
async def _require_list(db: AsyncSession, list_id: int) -> ShoppingList:
    """Load a list with its entries and their items, or 404.

    populate_existing makes a re-fetch after commit return fresh values (e.g. the
    bumped updated_at), which is what db.refresh() did for the sync session.
    """
    sl = (
        await db.execute(
            select(ShoppingList)
            .where(ShoppingList.id == list_id)
            .options(_LIST_WITH_ITEMS)
            .execution_options(populate_existing=True)
        )
    ).scalars().first()
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")
    return sl


# ai: claude-opus-5-5 | 2026-09-28
async def _require_entry(db: AsyncSession, list_id: int, entry_id: int) -> ShoppingListItem:
    """Load one list entry with its item, or 404."""
    sli = (
        await db.execute(
            select(ShoppingListItem)
            .where(ShoppingListItem.id == entry_id, ShoppingListItem.list_id == list_id)
            .options(selectinload(ShoppingListItem.item))
            .execution_options(populate_existing=True)
        )
    ).scalars().first()
    if sli is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List item not found")
    return sli


# ai: claude-opus-5-5 | 2026-09-28
def _build_item_out(sli: ShoppingListItem, latest: LatestPurchase | None) -> ShoppingListItemOut:
    item = sli.item
    latest_price = latest.price if latest else None
    latest_price_per_lb = latest.price_per_lb if latest else None
    cost = _estimated_cost(sli.quantity, item.is_by_weight, latest_price, latest_price_per_lb)
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
        estimated_cost=cost,
    )


# ai: claude-opus-5-5 | 2026-09-28
def _total_estimate(items_out: list[ShoppingListItemOut]) -> Decimal | None:
    costs = [i.estimated_cost for i in items_out if i.estimated_cost is not None]
    return sum(costs, Decimal("0")).quantize(Decimal("0.01")) if costs else None


# ai: claude-opus-5-5 | 2026-09-28
async def _build_list_out(sl: ShoppingList, db: AsyncSession) -> ShoppingListOut:
    latest = await latest_purchases(db, [sli.item_id for sli in sl.items])
    items_out = [_build_item_out(sli, latest.get(sli.item_id)) for sli in sl.items]
    return ShoppingListOut(
        id=sl.id,
        name=sl.name,
        created_at=sl.created_at,
        updated_at=sl.updated_at,
        items=items_out,
        total_estimate=_total_estimate(items_out),
    )


# ai: claude-opus-5-5 | 2026-09-28
async def _build_entry_out(sli: ShoppingListItem, db: AsyncSession) -> ShoppingListItemOut:
    latest = await latest_purchases(db, [sli.item_id])
    return _build_item_out(sli, latest.get(sli.item_id))


@router.get("", response_model=list[ShoppingListSummary])
async def list_shopping_lists(db: AsyncSession = Depends(get_db)) -> list[ShoppingListSummary]:
    # ai: claude-opus-5-5 | 2026-09-28
    lists = (
        await db.execute(
            select(ShoppingList)
            .options(_LIST_WITH_ITEMS)
            .order_by(ShoppingList.updated_at.desc())
        )
    ).scalars().all()
    # One price query covering every list, not one per list.
    latest = await latest_purchases(db, list({sli.item_id for sl in lists for sli in sl.items}))

    result = []
    for sl in lists:
        items_out = [_build_item_out(sli, latest.get(sli.item_id)) for sli in sl.items]  # ai: claude-opus-5-5 | 2026-09-28
        result.append(ShoppingListSummary(
            id=sl.id,
            name=sl.name,
            created_at=sl.created_at,
            updated_at=sl.updated_at,
            item_count=len(sl.items),
            total_estimate=_total_estimate(items_out),  # ai: claude-opus-5-5 | 2026-09-28
        ))
    return result


@router.post("", response_model=ShoppingListOut, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(
    payload: ShoppingListCreate, db: AsyncSession = Depends(get_db)
) -> ShoppingListOut:
    sl = ShoppingList(name=payload.name.strip() or "My List")
    db.add(sl)
    # ai: claude-opus-5-5 | 2026-09-28
    await db.commit()
    return await _build_list_out(await _require_list(db, sl.id), db)


@router.get("/{list_id}", response_model=ShoppingListOut)
async def get_shopping_list(list_id: int, db: AsyncSession = Depends(get_db)) -> ShoppingListOut:
    return await _build_list_out(await _require_list(db, list_id), db)  # ai: claude-opus-5-5 | 2026-09-28


@router.patch("/{list_id}", response_model=ShoppingListOut)
async def rename_shopping_list(
    list_id: int, payload: ShoppingListRename, db: AsyncSession = Depends(get_db)
) -> ShoppingListOut:
    sl = await _require_list(db, list_id)  # ai: claude-opus-5-5 | 2026-09-28
    sl.name = payload.name.strip() or sl.name
    # ai: claude-opus-5-5 | 2026-09-28
    await db.commit()
    return await _build_list_out(await _require_list(db, list_id), db)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(list_id: int, db: AsyncSession = Depends(get_db)) -> None:
    # ai: claude-opus-5-5 | 2026-09-28
    # Entries are loaded by _require_list so the delete-orphan cascade doesn't lazy-load.
    sl = await _require_list(db, list_id)
    await db.delete(sl)
    await db.commit()


@router.post("/{list_id}/items", response_model=ShoppingListItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    list_id: int, payload: ShoppingListItemAdd, db: AsyncSession = Depends(get_db)
) -> ShoppingListItemOut:
    await _require_list(db, list_id)  # ai: claude-opus-5-5 | 2026-09-28

    item = (await db.execute(select(Item).where(Item.id == payload.item_id))).scalars().first()  # ai: claude-opus-5-5 | 2026-09-28
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    sli = ShoppingListItem(
        list_id=list_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        note=payload.note,
    )
    db.add(sli)
    # ai: claude-opus-5-5 | 2026-09-28
    await db.commit()
    return await _build_entry_out(await _require_entry(db, list_id, sli.id), db)


@router.patch("/{list_id}/items/{entry_id}", response_model=ShoppingListItemOut)
async def update_item(
    list_id: int, entry_id: int, payload: ShoppingListItemUpdate, db: AsyncSession = Depends(get_db)
) -> ShoppingListItemOut:
    sli = await _require_entry(db, list_id, entry_id)  # ai: claude-opus-5-5 | 2026-09-28

    if payload.quantity is not None:
        sli.quantity = payload.quantity
    if payload.note is not None:
        sli.note = payload.note or None
    # ai: claude-opus-5-5 | 2026-09-28
    await db.commit()
    return await _build_entry_out(await _require_entry(db, list_id, entry_id), db)


@router.delete("/{list_id}/items/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(list_id: int, entry_id: int, db: AsyncSession = Depends(get_db)) -> None:
    sli = await _require_entry(db, list_id, entry_id)  # ai: claude-opus-5-5 | 2026-09-28
    await db.delete(sli)
    await db.commit()
