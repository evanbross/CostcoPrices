# ai: claude-sonnet-4-6 | 2026-06-18
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.schemas import ImportReport, ImportReportItem, PriceChange
from app.models.models import Item, PriceHistory, Receipt
from app.services.pricing import price_before_receipt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/receipt/{receipt_id}",
    response_model=ImportReport,
    status_code=status.HTTP_200_OK,
)
async def receipt_import_report(
    receipt_id: int, db: Session = Depends(get_db)
) -> ImportReport:
    """Return a comparison report for a specific receipt vs. prior price history."""
    receipt = db.execute(select(Receipt).where(Receipt.id == receipt_id)).scalars().first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    rows = (
        db.execute(
            select(PriceHistory, Item)
            .join(Item, PriceHistory.item_id == Item.id)
            .where(PriceHistory.receipt_id == receipt_id)
        )
        .all()
    )

    new_items: list[ImportReportItem] = []
    price_changes: list[PriceChange] = []
    unchanged: list[ImportReportItem] = []
    coupons: list[ImportReportItem] = []

    for ph, item in rows:
        report_item = ImportReportItem(
            item_id=item.id,
            item_code=item.item_code,
            description=item.description,
            friendly_name=item.friendly_name,
            price=ph.price,
        )

        if ph.is_coupon:
            coupons.append(report_item)
            continue

        # ai: claude-opus-5-5 | 2026-09-28
        # Compare against the purchase before this receipt's shopping date, not the
        # last-imported one (which can be a later trip if receipts arrive out of order).
        prev = price_before_receipt(db, item.id, receipt)

        if prev is None:
            new_items.append(report_item)
        elif prev != ph.price:
            price_changes.append(
                PriceChange(
                    item_id=item.id,
                    item_code=item.item_code,
                    description=item.description,
                    friendly_name=item.friendly_name,
                    old_price=prev,
                    new_price=ph.price,
                    change=ph.price - prev,
                )
            )
        else:
            unchanged.append(report_item)

    return ImportReport(
        receipt_id=receipt_id,
        new_items=new_items,
        price_changes=price_changes,
        unchanged=unchanged,
        coupons=coupons,
    )
