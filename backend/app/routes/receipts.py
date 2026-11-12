# ai: claude-sonnet-4-6 | 2026-06-19
import asyncio
import logging

import fitz  # pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError

from app.database.schemas import (
    ImportReport,
    OcrResponse,
    ReceiptConfirmRequest,
    ReceiptDetailOut,
    ReceiptOut,
)
from app.routes.dependencies import ReceiptServiceDep
from app.services import ocr_service

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


# ai: claude-opus-5-5 | 2026-09-29
@router.post("/confirm", response_model=ImportReport, status_code=status.HTTP_201_CREATED)
async def confirm_receipt(payload: ReceiptConfirmRequest, service: ReceiptServiceDep) -> ImportReport:
    """Save confirmed receipt line items and return an import report."""
    if not payload.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one line item is required.",
        )
    try:
        return await service.confirm(payload)
    except SQLAlchemyError:
        # The service has rolled back and logged the details; don't leak them to the client.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save receipt.",
        ) from None


# ai: claude-opus-5-5 | 2026-09-29
@router.get("", response_model=list[ReceiptOut], status_code=status.HTTP_200_OK)
async def list_receipts(service: ReceiptServiceDep) -> list[ReceiptOut]:
    return await service.list_receipts()


# ai: claude-opus-5-5 | 2026-09-29
@router.get("/{receipt_id}", response_model=ReceiptDetailOut, status_code=status.HTTP_200_OK)
async def get_receipt(receipt_id: int, service: ReceiptServiceDep) -> ReceiptDetailOut:
    return await service.get_receipt(receipt_id)
