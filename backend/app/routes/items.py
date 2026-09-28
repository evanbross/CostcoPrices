# ai: claude-sonnet-4-6 | 2026-06-18
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import ItemDetailOut, ItemOut, ItemUpdate, PriceHistoryOut, PriceHistoryUpdate
from app.models.models import Item, PriceHistory, Receipt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/items", tags=["items"])


# ai: claude-opus-5-5 | 2026-09-28
def _build_item_out(item: Item, latest_price: Decimal | None, last_purchased: date | None) -> ItemOut:
    return ItemOut(
        id=item.id,
        item_code=item.item_code,
        description=item.description,
        friendly_name=item.friendly_name,
        tax_type=item.tax_type,
        is_by_weight=item.is_by_weight,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_price=latest_price,
        last_purchased=last_purchased,
    )


# ai: claude-opus-5-5 | 2026-09-28
def _last_purchased_dates(db: Session, item_id: int | None = None) -> dict[int, date]:
    """Map item_id → most recent receipt shopping_date the item was bought on.

    Coupon lines are excluded: they're discounts applied to a purchase, not a
    purchase themselves. Pass item_id to limit the query to one item; omit it to
    get every item in a single grouped query.
    """
    stmt = (
        select(PriceHistory.item_id, func.max(Receipt.shopping_date))
        .join(Receipt, PriceHistory.receipt_id == Receipt.id)
        .where(PriceHistory.is_coupon.is_(False))
        .group_by(PriceHistory.item_id)
    )
    if item_id is not None:
        stmt = stmt.where(PriceHistory.item_id == item_id)
    return {row_item_id: shopping_date for row_item_id, shopping_date in db.execute(stmt).all()}


@router.get("", response_model=list[ItemOut], status_code=status.HTTP_200_OK)
async def list_items(db: Session = Depends(get_db)) -> list[ItemOut]:
    items = db.execute(
        select(Item).order_by(func.coalesce(Item.friendly_name, Item.description))
    ).scalars().all()
    last_purchased = _last_purchased_dates(db)  # ai: claude-opus-5-5 | 2026-09-28

    results = []
    for item in items:
        latest = (
            db.execute(
                select(PriceHistory.price)
                .where(
                    PriceHistory.item_id == item.id,
                    PriceHistory.is_coupon.is_(False),
                )
                .order_by(PriceHistory.created_at.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        results.append(_build_item_out(item, latest, last_purchased.get(item.id)))  # ai: claude-opus-5-5 | 2026-09-28
    return results


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
            .order_by(Receipt.shopping_date.asc())
        )
        .all()
    )

    history_out = [
        PriceHistoryOut(
            id=ph.id,
            receipt_id=ph.receipt_id,
            price=ph.price,
            is_coupon=ph.is_coupon,
            coupon_for_item_id=ph.coupon_for_item_id,
            created_at=ph.created_at,
            shopping_date=shopping_date,
        )
        for ph, shopping_date in history_rows
    ]

    latest = history_out[-1].price if history_out and not history_out[-1].is_coupon else None

    return ItemDetailOut(
        id=item.id,
        item_code=item.item_code,
        description=item.description,
        friendly_name=item.friendly_name,
        tax_type=item.tax_type,
        is_by_weight=item.is_by_weight,
        created_at=item.created_at,
        updated_at=item.updated_at,
        latest_price=latest,
        last_purchased=_last_purchased_dates(db, item_id).get(item_id),  # ai: claude-opus-5-5 | 2026-09-28
        price_history=history_out,
    )


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

    latest = (
        db.execute(
            select(PriceHistory.price)
            .where(PriceHistory.item_id == item.id, PriceHistory.is_coupon.is_(False))
            .order_by(PriceHistory.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return _build_item_out(item, latest, _last_purchased_dates(db, item.id).get(item.id))  # ai: claude-opus-5-5 | 2026-09-28
