# ai: claude-opus-5-5 | 2026-09-29
from fastapi import APIRouter, status

from app.database.schemas import ImportReport
from app.routes.dependencies import ReceiptServiceDep

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get(
    "/receipt/{receipt_id}",
    response_model=ImportReport,
    status_code=status.HTTP_200_OK,
)
async def receipt_import_report(
    receipt_id: int, service: ReceiptServiceDep
) -> ImportReport:
    """Return a comparison report for a specific receipt vs. prior price history."""
    return await service.import_report(receipt_id)
