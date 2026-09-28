# ai: claude-sonnet-4-6 | 2026-06-18
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import ItemDetailOut, ItemOut, ItemUpdate, PriceHistoryOut, PriceHistoryUpdate
from app.models.models import Item, PriceHistory, Receipt
from app.services.pricing import LatestPurchase, latest_purchases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"])


# ai: claude-opus-5-5 | 2026-09-28
def _build_item_out(item: Item, latest: LatestPurchase | None) -> ItemOut:
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


@router.get("", response_model=list[ItemOut], status_code=status.HTTP_200_OK)
async def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    items = db.execute(
        select(Item).order_by(func.coalesce(Item.friendly_name, Item.description))
    ).scalars().all()
    # ai: claude-opus-5-5 | 2026-09-28
    latest = latest_purchases(db)
    return [_build_item_out(item, latest.get(item.id)) for item in items]


@router.get("/{item_id}", response_model=ItemDetailOut, status_code=status.HTTP_200_OK)
async def get_item(item_id: int, db: Session = Depends(get_db)) -> ItemDetailOut:
    item = db.execute(select(Item).where(Item.id == item_id)).scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    history_rows = (
        db.execute(
            select(PriceHistory, Receipt.shopping_date)
            .join(Receipt, PriceHistory.receipt_id == Receipt.id)
            .where(PriceHistory.item_id == item_id)
            .order_by(Receipt.shopping_date.asc(), Receipt.id.asc(), PriceHistory.id.asc())  # ai: claude-opus-5-5 | 2026-09-28
        )
        .all()
    )

    history_out = [
        PriceHistoryOut(
            id=ph.id,
            receipt_id=ph.receipt_id,
            price=ph.price,
            price_per_lb=ph.price_per_lb,  # ai: claude-opus-5-5 | 2026-09-28 — was omitted, so saved $/lb vanished on reload
            is_coupon=ph.is_coupon,
            coupon_for_item_id=ph.coupon_for_item_id,
            created_at=ph.created_at,
            shopping_date=shopping_date,
        )
        for ph, shopping_date in history_rows
    ]

    # ai: claude-opus-5-5 | 2026-09-28
    # The last history row can be a coupon, so don't read "latest" off it.
    item_out = _build_item_out(item, latest_purchases(db, [item_id]).get(item_id))
    return ItemDetailOut(**item_out.model_dump(), price_history=history_out)


@router.patch("/history/{entry_id}", response_model=PriceHistoryOut, status_code=status.HTTP_200_OK)
async def update_price_history_entry(
    entry_id: int, payload: PriceHistoryUpdate, db: Session = Depends(get_db)
) -> PriceHistoryOut:
    """Set or clear price_per_lb on a price history entry (for by-weight items)."""
    ph = db.execute(select(PriceHistory).where(PriceHistory.id == entry_id)).scalars().first()
    if ph is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price history entry not found")

    ph.price_per_lb = payload.price_per_lb
    db.commit()
    db.refresh(ph)

    shopping_date = db.execute(
        select(Receipt.shopping_date).where(Receipt.id == ph.receipt_id)
    ).scalar_one_or_none()

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


@router.patch("/{item_id}", response_model=ItemOut, status_code=status.HTTP_200_OK)
async def update_item(
    item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)
) -> ItemOut:
    item = db.execute(select(Item).where(Item.id == item_id)).scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    if payload.friendly_name is not None:
        item.friendly_name = payload.friendly_name
    if payload.tax_type is not None:
        item.tax_type = payload.tax_type
    if payload.is_by_weight is not None:
        item.is_by_weight = payload.is_by_weight

    db.commit()
    db.refresh(item)

    return _build_item_out(item, latest_purchases(db, [item.id]).get(item.id))  # ai: claude-opus-5-5 | 2026-09-28
