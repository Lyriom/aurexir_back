from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import new_uuid, utcnow
from app.models.product import Product
from app.models.user import User

ORDER_STATUSES = ("pending", "paid", "shipped", "delivered", "canceled")

# Transiciones válidas de estado (ver PATCH /admin/orders/{id}).
VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "canceled"},
    "paid": {"shipped", "canceled"},
    "shipped": {"delivered", "canceled"},
    "delivered": set(),
    "canceled": set(),
}

# Estados que cuentan como venta efectiva (métricas) y que ya descontaron stock.
PAID_STATUSES = ("paid", "shipped", "delivered")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # AX-1042
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount_code: Mapped[str | None] = mapped_column(String(20))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    shipping_method: Mapped[str] = mapped_column(String(20))  # standard | express
    shipping_address: Mapped[dict | None] = mapped_column(JSON)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_payment_intent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    name_snapshot: Mapped[str] = mapped_column(String(200))
    brand_snapshot: Mapped[str] = mapped_column(String(120))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # precio al comprar
    qty: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
