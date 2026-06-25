# ai: claude-sonnet-4-6 | 2026-06-18
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(200))
    friendly_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_type: Mapped[str | None] = mapped_column(String(1), nullable=True)
    is_by_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory",
        back_populates="item",
        foreign_keys="PriceHistory.item_id",
        order_by="PriceHistory.created_at",
    )


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    barcode: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    shopping_date: Mapped[date] = mapped_column(Date, index=True)
    store_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="receipt"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_per_lb: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    is_coupon: Mapped[bool] = mapped_column(Boolean, default=False)
    coupon_for_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    item: Mapped["Item"] = relationship(
        "Item", back_populates="price_history", foreign_keys=[item_id]
    )
    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="price_history")
    coupon_for_item: Mapped["Item | None"] = relationship(
        "Item", foreign_keys=[coupon_for_item_id]
    )


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    items: Mapped[list["ShoppingListItem"]] = relationship(
        "ShoppingListItem", back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=Decimal("1"))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    shopping_list: Mapped["ShoppingList"] = relationship("ShoppingList", back_populates="items")
    item: Mapped["Item"] = relationship("Item")
