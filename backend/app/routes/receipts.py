# ai: claude-sonnet-4-6 | 2026-06-19
import asyncio
import logging

import fitz  # pymupdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.database.schemas import (
    ImportReport,
    OcrResponse,
    ReceiptConfirmRequest,
    ReceiptDetailOut,
    ReceiptLineOut,
    ReceiptOut,
)
from app.models.models import Item, PriceHistory, Receipt
from app.services import ocr_service, receipt_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}

_PDF_CONTENT_TYPES = {"application/pdf"}

_PDF_RENDER_DPI = 150  # good balance of quality vs. payload size


# ai: claude-opus-5-5 | 2026-09-28
def _pdf_to_png_pages(pdf_bytes: bytes) -> list[bytes]:
    """Render each page of a PDF to a PNG byte string.

    CPU-bound and synchronous: call it via asyncio.to_thread from async code.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [page.get_pixmap(dpi=_PDF_RENDER_DPI).tobytes("png") for page in doc]


@router.post("/upload", response_model=OcrResponse, status_code=status.HTTP_200_OK)
async def upload_receipt(image: UploadFile = File(...)) -> OcrResponse:
    """Accept a receipt screenshot or PDF, run OCR, return parsed data for user review.
    Nothing is saved to the database at this step.
    """
    content_type = image.content_type or ""

    is_pdf = content_type in _PDF_CONTENT_TYPES
    media_type = _ALLOWED_IMAGE_TYPES.get(content_type)

    if not is_pdf and media_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Use JPEG, PNG, WebP, GIF, or PDF.",
        )

    file_bytes = await image.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File must be ≤ 20 MB.",
        )

    try:
        if is_pdf:
            png_pages = await asyncio.to_thread(_pdf_to_png_pages, file_bytes)  # ai: claude-opus-5-5 | 2026-09-28 — keep the event loop free
            if not png_pages:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PDF appears to be empty (no pages found).",
                )
            images = [(page, "image/png") for page in png_pages]
            return await ocr_service.parse_receipt_images(images)
        else:
            return await ocr_service.parse_receipt_image(file_bytes, media_type)  # type: ignore[arg-type]
    except HTTPException:
        raise
    except ValueError as exc:
        logger.error("OCR failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.post("/confirm", response_model=ImportReport, status_code=status.HTTP_201_CREATED)
async def confirm_receipt(
    payload: ReceiptConfirmRequest, db: AsyncSession = Depends(get_db)  # ai: claude-opus-5-5 | 2026-09-28 — async session
) -> ImportReport:
    """Save confirmed receipt line items and return an import report."""
    if not payload.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one line item is required.",
        )

    # Duplicate barcode check — reject before touching any data
    if payload.barcode:
        existing = (await db.execute(
            select(Receipt).where(Receipt.barcode == payload.barcode)
        )).scalars().first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Receipt with barcode {payload.barcode} was already imported (receipt #{existing.id}, {existing.shopping_date}).",
            )

    try:
        report = await receipt_service.confirm_receipt(
            db=db,
            shopping_date=payload.shopping_date,
            store_location=payload.store_location,
            notes=payload.notes,
            barcode=payload.barcode,
            lines=payload.lines,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("confirm_receipt failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save receipt.",
        )

    return report


@router.get("", response_model=list[ReceiptOut], status_code=status.HTTP_200_OK)
async def list_receipts(db: AsyncSession = Depends(get_db)) -> list[ReceiptOut]:  # ai: claude-opus-5-5 | 2026-09-28 — async session
    # ai: claude-opus-5-5 | 2026-09-28
    # One grouped query for every receipt's line count instead of one count query per receipt.
    line_counts = (
        select(PriceHistory.receipt_id, func.count().label("line_count"))
        .group_by(PriceHistory.receipt_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Receipt, func.coalesce(line_counts.c.line_count, 0))
            .outerjoin(line_counts, line_counts.c.receipt_id == Receipt.id)
            .order_by(Receipt.shopping_date.desc())
        )
    ).all()

    return [
        ReceiptOut(
            id=r.id,
            barcode=r.barcode,
            shopping_date=r.shopping_date,
            store_location=r.store_location,
            notes=r.notes,
            created_at=r.created_at,
            line_count=count,
        )
        for r, count in rows
    ]


@router.get("/{receipt_id}", response_model=ReceiptDetailOut, status_code=status.HTTP_200_OK)
async def get_receipt(receipt_id: int, db: AsyncSession = Depends(get_db)) -> ReceiptDetailOut:  # ai: claude-opus-5-5 | 2026-09-28 — async session
    receipt = (await db.execute(select(Receipt).where(Receipt.id == receipt_id))).scalars().first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")

    rows = (
        await db.execute(
            select(PriceHistory, Item)
            .join(Item, PriceHistory.item_id == Item.id)
            .where(PriceHistory.receipt_id == receipt_id)
            .order_by(PriceHistory.id)
        )
    ).all()

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
        for ph, item in rows
    ]

    return ReceiptDetailOut(
        id=receipt.id,
        barcode=receipt.barcode,
        shopping_date=receipt.shopping_date,
        store_location=receipt.store_location,
        notes=receipt.notes,
        created_at=receipt.created_at,
        line_count=len(lines),
        lines=lines,
    )
