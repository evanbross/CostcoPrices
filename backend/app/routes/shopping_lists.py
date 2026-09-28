# ai: claude-sonnet-4-6 | 2026-06-20
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

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
def _build_items_out(slis: list[ShoppingListItem], db: Session) -> list[ShoppingListItemOut]:
    """Build list entries with prices fetched in one query for all of them."""
    latest = latest_purchases(db, [sli.item_id for sli in slis])
    return [_build_item_out(sli, latest.get(sli.item_id)) for sli in slis]


def _build_list_out(sl: ShoppingList, db: Session) -> ShoppingListOut:
    items_out = _build_items_out(sl.items, db)  # ai: claude-opus-5-5 | 2026-09-28
    costs = [i.estimated_cost for i in items_out if i.estimated_cost is not None]
    total = sum(costs, Decimal("0")).quantize(Decimal("0.01")) if costs else None
    return ShoppingListOut(
        id=sl.id,
        name=sl.name,
        created_at=sl.created_at,
        updated_at=sl.updated_at,
        items=items_out,
        total_estimate=total,
    )


@router.get("", response_model=list[ShoppingListSummary])
async def list_shopping_lists(db: Session = Depends(get_db)) -> list[ShoppingListSummary]:
    lists = db.execute(
        select(ShoppingList).order_by(ShoppingList.updated_at.desc())
    ).scalars().all()

    result = []
    for sl in lists:
        items_out = _build_items_out(sl.items, db)  # ai: claude-opus-5-5 | 2026-09-28
        costs = [i.estimated_cost for i in items_out if i.estimated_cost is not None]
        total = sum(costs, Decimal("0")).quantize(Decimal("0.01")) if costs else None
        result.append(ShoppingListSummary(
            id=sl.id,
            name=sl.name,
            created_at=sl.created_at,
            updated_at=sl.updated_at,
            item_count=len(sl.items),
            total_estimate=total,
        ))
    return result


@router.post("", response_model=ShoppingListOut, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(
    payload: ShoppingListCreate, db: Session = Depends(get_db)
) -> ShoppingListOut:
    sl = ShoppingList(name=payload.name.strip() or "My List")
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return _build_list_out(sl, db)


@router.get("/{list_id}", response_model=ShoppingListOut)
async def get_shopping_list(list_id: int, db: Session = Depends(get_db)) -> ShoppingListOut:
    sl = db.execute(select(ShoppingList).where(ShoppingList.id == list_id)).scalars().first()
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")
    return _build_list_out(sl, db)


@router.patch("/{list_id}", response_model=ShoppingListOut)
async def rename_shopping_list(
    list_id: int, payload: ShoppingListRename, db: Session = Depends(get_db)
) -> ShoppingListOut:
    sl = db.execute(select(ShoppingList).where(ShoppingList.id == list_id)).scalars().first()
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")
    sl.name = payload.name.strip() or sl.name
    db.commit()
    db.refresh(sl)
    return _build_list_out(sl, db)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(list_id: int, db: Session = Depends(get_db)) -> None:
    sl = db.execute(select(ShoppingList).where(ShoppingList.id == list_id)).scalars().first()
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")
    db.delete(sl)
    db.commit()


@router.post("/{list_id}/items", response_model=ShoppingListItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(
    list_id: int, payload: ShoppingListItemAdd, db: Session = Depends(get_db)
) -> ShoppingListItemOut:
    sl = db.execute(select(ShoppingList).where(ShoppingList.id == list_id)).scalars().first()
    if sl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopping list not found")

    item = db.execute(select(Item).where(Item.id == payload.item_id)).scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    sli = ShoppingListItem(
        list_id=list_id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        note=payload.note,
    )
    db.add(sli)
    db.commit()
    db.refresh(sli)
    return _build_items_out([sli], db)[0]  # ai: claude-opus-5-5 | 2026-09-28


@router.patch("/{list_id}/items/{entry_id}", response_model=ShoppingListItemOut)
async def update_item(
    list_id: int, entry_id: int, payload: ShoppingListItemUpdate, db: Session = Depends(get_db)
) -> ShoppingListItemOut:
    sli = db.execute(
        select(ShoppingListItem).where(
            ShoppingListItem.id == entry_id, ShoppingListItem.list_id == list_id
        )
    ).scalars().first()
    if sli is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List item not found")

    if payload.quantity is not None:
        sli.quantity = payload.quantity
    if payload.note is not None:
        sli.note = payload.note or None
    db.commit()
    db.refresh(sli)
    return _build_items_out([sli], db)[0]  # ai: claude-opus-5-5 | 2026-09-28


@router.delete("/{list_id}/items/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(list_id: int, entry_id: int, db: Session = Depends(get_db)) -> None:
    sli = db.execute(
        select(ShoppingListItem).where(
            ShoppingListItem.id == entry_id, ShoppingListItem.list_id == list_id
        )
    ).scalars().first()
    if sli is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List item not found")
    db.delete(sli)
    db.commit()
