# ai: claude-opus-5-5 | 2026-09-29
from fastapi import APIRouter, status

from app.database.schemas import (
    ShoppingListCreate,
    ShoppingListItemAdd,
    ShoppingListItemOut,
    ShoppingListItemUpdate,
    ShoppingListOut,
    ShoppingListRename,
    ShoppingListSummary,
)
from app.routes.dependencies import ShoppingListServiceDep

router = APIRouter(prefix="/api/shopping-lists", tags=["shopping-lists"])


@router.get("", response_model=list[ShoppingListSummary])
async def list_shopping_lists(service: ShoppingListServiceDep) -> list[ShoppingListSummary]:
    return await service.list_summaries()


@router.post("", response_model=ShoppingListOut, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(payload: ShoppingListCreate, service: ShoppingListServiceDep) -> ShoppingListOut:
    return await service.create_list(payload.name)


@router.get("/{list_id}", response_model=ShoppingListOut)
async def get_shopping_list(list_id: int, service: ShoppingListServiceDep) -> ShoppingListOut:
    return await service.get_list(list_id)


@router.patch("/{list_id}", response_model=ShoppingListOut)
async def rename_shopping_list(list_id: int, payload: ShoppingListRename, service: ShoppingListServiceDep) -> ShoppingListOut:
    return await service.rename_list(list_id, payload.name)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(list_id: int, service: ShoppingListServiceDep) -> None:
    await service.delete_list(list_id)


@router.post("/{list_id}/items", response_model=ShoppingListItemOut, status_code=status.HTTP_201_CREATED)
async def add_item(list_id: int, payload: ShoppingListItemAdd, service: ShoppingListServiceDep) -> ShoppingListItemOut:
    return await service.add_entry(list_id, payload)


@router.patch("/{list_id}/items/{entry_id}", response_model=ShoppingListItemOut)
async def update_item(
    list_id: int, entry_id: int, payload: ShoppingListItemUpdate, service: ShoppingListServiceDep
) -> ShoppingListItemOut:
    return await service.update_entry(list_id, entry_id, payload)


@router.delete("/{list_id}/items/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(list_id: int, entry_id: int, service: ShoppingListServiceDep) -> None:
    await service.remove_entry(list_id, entry_id)
