# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-29
"""FastAPI dependencies that hand each request a service bound to its DB session."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services.item_service import ItemService
from app.services.receipt_service import ReceiptService
from app.services.shopping_list_service import ShoppingListService


async def get_item_service(db: AsyncSession = Depends(get_db)) -> ItemService:
    return ItemService(db)


async def get_receipt_service(db: AsyncSession = Depends(get_db)) -> ReceiptService:
    return ReceiptService(db)


async def get_shopping_list_service(db: AsyncSession = Depends(get_db)) -> ShoppingListService:
    return ShoppingListService(db)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
ReceiptServiceDep = Annotated[ReceiptService, Depends(get_receipt_service)]
ShoppingListServiceDep = Annotated[ShoppingListService, Depends(get_shopping_list_service)]
