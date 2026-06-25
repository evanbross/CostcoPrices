# ai: claude-sonnet-4-6 | 2026-06-18
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.schemas import (
    ImportReport,
    ImportReportItem,
    ParsedLine,
    PriceChange,
)
from app.models.models import Item, PriceHistory, Receipt

logger = logging.getLogger(__name__)


def _latest_price(db: Session, item_id: int) -> Decimal | None:
    """Return the most recent non-coupon price for an item, or None."""
    row = (
        db.execute(
            select(PriceHistory.price)
            .where(PriceHistory.item_id == item_id, PriceHistory.is_coupon.is_(False))
            .order_by(PriceHistory.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    return row


def confirm_receipt(
    db: Session,
    shopping_date: date,
    store_location: str | None,
    notes: str | None,
    barcode: str | None,
    lines: list[ParsedLine],
) -> ImportReport:
    """Persist a confirmed receipt and return an import report.

    Caller is responsible for db.commit().
    """
    receipt = Receipt(
        shopping_date=shopping_date,
        store_location=store_location,
        notes=notes,
        barcode=barcode or None,
    )
    db.add(receipt)
    db.flush()  # populate receipt.id without committing

    new_items: list[ImportReportItem] = []
    price_changes: list[PriceChange] = []
    unchanged: list[ImportReportItem] = []
    coupons: list[ImportReportItem] = []

    # Build a lookup map for coupon resolution after processing all regular lines
    item_code_to_id: dict[str, int] = {}

    for line in lines:
        if line.is_coupon:
            continue  # process coupons in second pass

        existing = db.execute(
            select(Item).where(Item.item_code == line.item_code)
        ).scalars().first()

        if existing is None:
            item = Item(
                item_code=line.item_code,
                description=line.description,
                tax_type=line.tax_type,
            )
            db.add(item)
            db.flush()
            is_new = True
        else:
            item = existing
            if existing.description != line.description:
                existing.description = line.description
            if line.tax_type and existing.tax_type != line.tax_type:
                existing.tax_type = line.tax_type
            is_new = False

        item_code_to_id[line.item_code] = item.id

        old_price = None if is_new else _latest_price(db, item.id)

        ph = PriceHistory(
            item_id=item.id,
            receipt_id=receipt.id,
            price=line.price,
            is_coupon=False,
        )
        db.add(ph)

        report_item = ImportReportItem(
            item_id=item.id,
            item_code=item.item_code,
            description=item.description,
            friendly_name=item.friendly_name,
            price=line.price,
        )

        if is_new:
            new_items.append(report_item)
        elif old_price is not None and old_price != line.price:
            price_changes.append(
                PriceChange(
                    item_id=item.id,
                    item_code=item.item_code,
                    description=item.description,
                    friendly_name=item.friendly_name,
                    old_price=old_price,
                    new_price=line.price,
                    change=line.price - old_price,
                )
            )
        else:
            unchanged.append(report_item)

    # Second pass: coupons
    for line in lines:
        if not line.is_coupon:
            continue

        coupon_item = db.execute(
            select(Item).where(Item.item_code == line.item_code)
        ).scalars().first()

        if coupon_item is None:
            coupon_item = Item(
                item_code=line.item_code,
                description=line.description or f"COUPON {line.item_code}",
                tax_type=line.tax_type,
            )
            db.add(coupon_item)
            db.flush()

        coupon_for_id = (
            item_code_to_id.get(line.coupon_for_code)
            if line.coupon_for_code
            else None
        )

        # Auto-set friendly_name on new coupon items (don't overwrite if already set)
        if coupon_item.friendly_name is None and coupon_for_id is not None:
            parent = db.execute(select(Item).where(Item.id == coupon_for_id)).scalars().first()
            if parent:
                coupon_item.friendly_name = f"Coupon for {parent.friendly_name or parent.description}"

        ph = PriceHistory(
            item_id=coupon_item.id,
            receipt_id=receipt.id,
            price=line.price,
            is_coupon=True,
            coupon_for_item_id=coupon_for_id,
        )
        db.add(ph)

        coupons.append(
            ImportReportItem(
                item_id=coupon_item.id,
                item_code=coupon_item.item_code,
                description=coupon_item.description,
                friendly_name=coupon_item.friendly_name,
                price=line.price,
            )
        )

    logger.info(
        "Receipt %d: %d new, %d changed, %d unchanged, %d coupons",
        receipt.id,
        len(new_items),
        len(price_changes),
        len(unchanged),
        len(coupons),
    )

    return ImportReport(
        receipt_id=receipt.id,
        new_items=new_items,
        price_changes=price_changes,
        unchanged=unchanged,
        coupons=coupons,
    )
