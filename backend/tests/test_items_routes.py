# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: gpt-5 | 2026-11-03
"""Item API integration tests against a fresh SQLite schema."""
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.main import app
from app.models.models import Item, PriceHistory, Receipt


async def test_create_item_and_reject_duplicate_code(db: AsyncSession) -> None:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/items",
                json={
                    "item_code": " 12345 ",
                    "description": " ROTISSERIE CHICKEN ",
                    "friendly_name": " Chicken ",
                    "tax_type": "3",
                    "is_by_weight": False,
                },
            )

            assert response.status_code == 201
            assert response.json()["item_code"] == "12345"
            assert response.json()["description"] == "ROTISSERIE CHICKEN"
            assert response.json()["friendly_name"] == "Chicken"
            assert response.json()["latest_price"] is None

            duplicate = await client.post(
                "/api/items",
                json={"item_code": "12345", "description": "Duplicate"},
            )

            assert duplicate.status_code == 409
            assert duplicate.json() == {"detail": "Item code 12345 already exists"}
    finally:
        app.dependency_overrides.clear()


async def test_create_item_rejects_blank_required_fields(db: AsyncSession) -> None:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/items",
                json={"item_code": "   ", "description": "   "},
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_update_item_changes_latest_purchase_price(db: AsyncSession) -> None:
    item = Item(item_code="777", description="COFFEE")
    receipt = Receipt(shopping_date=date(2026, 11, 1))
    db.add_all([item, receipt])
    await db.flush()
    price_entry = PriceHistory(
        item_id=item.id,
        receipt_id=receipt.id,
        price=Decimal("12.99"),
        is_coupon=False,
    )
    db.add(price_entry)
    await db.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                f"/api/items/{item.id}",
                json={"friendly_name": "Coffee", "latest_price": "10.49"},
            )

        assert response.status_code == 200
        assert response.json()["friendly_name"] == "Coffee"
        assert response.json()["latest_price"] == "10.49"
        await db.refresh(price_entry)
        assert price_entry.price == Decimal("10.49")
    finally:
        app.dependency_overrides.clear()


async def test_update_manually_created_item_sets_fallback_price(db: AsyncSession) -> None:
    item = Item(item_code="888", description="MANUAL ITEM")
    db.add(item)
    await db.commit()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.patch(
                f"/api/items/{item.id}",
                json={"latest_price": "8.75"},
            )
            list_response = await client.get("/api/items")

        assert response.status_code == 200
        assert response.json()["latest_price"] == "8.75"
        assert response.json()["last_purchased"] is None
        assert list_response.json()[0]["latest_price"] == "8.75"
        await db.refresh(item)
        assert item.manual_price == Decimal("8.75")
    finally:
        app.dependency_overrides.clear()
