# ai: claude-sonnet-4-6 | 2026-06-18
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.schemas import (
    ImportReport,
    ImportReportItem,
    ParsedLine,
    PriceChange,
    ReceiptConfirmRequest,
    ReceiptDetailOut,
    ReceiptLineOut,
    ReceiptOut,
)
from app.models.models import Item, PriceHistory, Receipt
from app.services.errors import ConflictError, NotFoundError
from app.services.pricing import price_before_receipt

logger = logging.getLogger(__name__)


# ai: claude-opus-5-5 | 2026-09-29
def _receipt_out(receipt: Receipt, line_count: int) -> ReceiptOut:
    return ReceiptOut(
        id=receipt.id,
        barcode=receipt.barcode,
        shopping_date=receipt.shopping_date,
        store_location=receipt.store_location,
        notes=receipt.notes,
        created_at=receipt.created_at,
        line_count=line_count,
    )


# ai: claude-opus-5-5 | 2026-09-29
class ReceiptService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_receipts(self) -> list[ReceiptOut]:
        # One grouped query for every receipt's line count instead of one per receipt.
        line_counts = (
            select(PriceHistory.receipt_id, func.count().label("line_count"))
            .group_by(PriceHistory.receipt_id)
            .subquery()
        )
        rows = (
            await self._db.execute(
                select(Receipt, func.coalesce(line_counts.c.line_count, 0))
                .outerjoin(line_counts, line_counts.c.receipt_id == Receipt.id)
                .order_by(Receipt.shopping_date.desc())
            )
        ).all()
        return [_receipt_out(receipt, count) for receipt, count in rows]

    async def get_receipt(self, receipt_id: int) -> ReceiptDetailOut:
        receipt = await self._require_receipt(receipt_id)
        lines = [
            ReceiptLineOut(
                id=ph.id,
                item_id=ph.item_id,
                item_code=item.item_code,
                description=item.description,
                friendly_name=item.friendly_name,
                price=ph.price,
                is_coupon=ph.is_coupon,
                coupon_for_item_id=ph.coupon_for_item_id,
            )
            for ph, item in await self._lines_with_items(receipt_id)
        ]
        return ReceiptDetailOut(**_receipt_out(receipt, len(lines)).model_dump(), lines=lines)

    async def import_report(self, receipt_id: int) -> ImportReport:
        """Compare a receipt's lines against each item's price before that trip."""
        return await self._build_report(await self._require_receipt(receipt_id))

    async def confirm(self, request: ReceiptConfirmRequest) -> ImportReport:
        """Save a user-confirmed receipt and return its import report, in one transaction."""
        await self._reject_duplicate_barcode(request.barcode)
        try:
            receipt = await self._save_lines(request)
            await self._db.flush()
            # Built from the saved rows by the same code as GET /api/reports/receipt/{id},
            # so the report shown right after import can't disagree with the stored one.
            report = await self._build_report(receipt)
            await self._db.commit()
        except SQLAlchemyError:
            await self._db.rollback()
            logger.exception("Saving receipt dated %s failed", request.shopping_date)
            raise
        logger.info(
            "Receipt %d: %d new, %d changed, %d unchanged, %d coupons",
            report.receipt_id,
            len(report.new_items),
            len(report.price_changes),
            len(report.unchanged),
            len(report.coupons),
        )
        return report

    async def _require_receipt(self, receipt_id: int) -> Receipt:
        receipt = await self._db.get(Receipt, receipt_id)
        if receipt is None:
            raise NotFoundError("Receipt not found")
        return receipt

    async def _lines_with_items(self, receipt_id: int) -> list[tuple[PriceHistory, Item]]:
        rows = (
            await self._db.execute(
                select(PriceHistory, Item)
                .join(Item, PriceHistory.item_id == Item.id)
                .where(PriceHistory.receipt_id == receipt_id)
                .order_by(PriceHistory.id)
            )
        ).all()
        return [(ph, item) for ph, item in rows]

    async def _reject_duplicate_barcode(self, barcode: str | None) -> None:
        if not barcode:
            return
        existing = (
            await self._db.execute(select(Receipt).where(Receipt.barcode == barcode))
        ).scalars().first()
        if existing is not None:
            raise ConflictError(
                f"Receipt with barcode {barcode} was already imported "
                f"(receipt #{existing.id}, {existing.shopping_date})."
            )

    async def _build_report(self, receipt: Receipt) -> ImportReport:
        new_items: list[ImportReportItem] = []
        price_changes: list[PriceChange] = []
        unchanged: list[ImportReportItem] = []
        coupons: list[ImportReportItem] = []

        for ph, item in await self._lines_with_items(receipt.id):
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

            # Compare against the purchase before this receipt's shopping date, not the
            # last-imported one (which can be a later trip if receipts arrive out of order).
            # None means this is the item's first purchase — including a known item whose
            # only other purchases are on later trips — so it's reported as new.
            prev = await price_before_receipt(self._db, item.id, receipt)
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
            receipt_id=receipt.id,
            new_items=new_items,
            price_changes=price_changes,
            unchanged=unchanged,
            coupons=coupons,
        )

    async def _save_lines(self, request: ReceiptConfirmRequest) -> Receipt:
        """Insert the receipt, its items (creating or updating them) and its price lines.

        Doesn't commit; confirm() owns the transaction.
        """
        receipt = Receipt(
            shopping_date=request.shopping_date,
            store_location=request.store_location,
            notes=request.notes,
            barcode=request.barcode or None,
        )
        self._db.add(receipt)
        await self._db.flush()  # populate receipt.id without committing

        # Lookup map for coupon resolution after processing all regular lines
        item_code_to_id: dict[str, int] = {}

        # ai: claude-sonnet-5 | 2026-07-20
        # Some coupon lines reference the discounted item by description text (e.g. "/KS KCUPS")
        # instead of its numeric item_code, so item_code_to_id can't resolve them. Fall back to
        # whichever non-coupon line immediately precedes the coupon in original receipt order.
        fallback_code_by_index: dict[int, str | None] = {}
        last_item_code: str | None = None
        for idx, line in enumerate(request.lines):
            if line.is_coupon:
                fallback_code_by_index[idx] = last_item_code
            else:
                last_item_code = line.item_code

        # ai: claude-opus-5-5 | 2026-09-29
        for line in request.lines:
            if line.is_coupon:
                continue  # process coupons in second pass
            item = await self._upsert_item(line)
            item_code_to_id[line.item_code] = item.id
            self._db.add(PriceHistory(item_id=item.id, receipt_id=receipt.id, price=line.price, is_coupon=False))

        # Second pass: coupons
        for idx, line in enumerate(request.lines):
            if not line.is_coupon:
                continue

            coupon_item = await self._item_by_code(line.item_code)
            if coupon_item is None:
                coupon_item = Item(
                    item_code=line.item_code,
                    description=line.description or f"COUPON {line.item_code}",
                    tax_type=line.tax_type,
                )
                self._db.add(coupon_item)
                await self._db.flush()

            coupon_for_id = item_code_to_id.get(line.coupon_for_code) if line.coupon_for_code else None
            if coupon_for_id is None:
                fallback_code = fallback_code_by_index.get(idx)
                if fallback_code:
                    coupon_for_id = item_code_to_id.get(fallback_code)

            # Auto-set friendly_name on new coupon items (don't overwrite if already set)
            if coupon_item.friendly_name is None and coupon_for_id is not None:
                parent = await self._db.get(Item, coupon_for_id)
                if parent:
                    coupon_item.friendly_name = f"Coupon for {parent.friendly_name or parent.description}"

            self._db.add(
                PriceHistory(
                    item_id=coupon_item.id,
                    receipt_id=receipt.id,
                    price=line.price,
                    is_coupon=True,
                    coupon_for_item_id=coupon_for_id,
                )
            )

        return receipt

    async def _item_by_code(self, item_code: str) -> Item | None:
        return (await self._db.execute(select(Item).where(Item.item_code == item_code))).scalars().first()

    async def _upsert_item(self, line: ParsedLine) -> Item:
        """Return the item for a receipt line, creating it or refreshing its receipt text."""
        item = await self._item_by_code(line.item_code)
        if item is None:
            item = Item(item_code=line.item_code, description=line.description, tax_type=line.tax_type)
            self._db.add(item)
            await self._db.flush()
            return item
        if item.description != line.description:
            item.description = line.description
        if line.tax_type and item.tax_type != line.tax_type:
            item.tax_type = line.tax_type
        return item
