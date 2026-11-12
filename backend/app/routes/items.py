# ai: claude-opus-5-5 | 2026-09-29
from fastapi import APIRouter, status

from app.database.schemas import ItemCreate, ItemDetailOut, ItemOut, ItemUpdate, PriceHistoryOut, PriceHistoryUpdate
from app.routes.dependencies import ItemServiceDep

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemOut], status_code=status.HTTP_200_OK)
async def list_items(service: ItemServiceDep) -> list[ItemOut]:
    return await service.list_items()


# ai: gpt-5 | 2026-11-03
@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(payload: ItemCreate, service: ItemServiceDep) -> ItemOut:
    return await service.create_item(payload)


@router.get("/{item_id}", response_model=ItemDetailOut, status_code=status.HTTP_200_OK)
async def get_item(item_id: int, service: ItemServiceDep) -> ItemDetailOut:
    return await service.get_item(item_id)


@router.patch("/history/{entry_id}", response_model=PriceHistoryOut, status_code=status.HTTP_200_OK)
async def update_price_history_entry(entry_id: int, payload: PriceHistoryUpdate, service: ItemServiceDep) -> PriceHistoryOut:
    """Set or clear price_per_lb on a price history entry (for by-weight items)."""
    return await service.update_price_history_entry(entry_id, payload)


@router.patch("/{item_id}", response_model=ItemOut, status_code=status.HTTP_200_OK)
async def update_item(item_id: int, payload: ItemUpdate, service: ItemServiceDep) -> ItemOut:
    return await service.update_item(item_id, payload)
