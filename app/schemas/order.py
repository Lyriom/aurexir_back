from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import Order, OrderItem
from app.schemas.auth import UserOut


class OrderItemOut(BaseModel):
    id: str  # slug del producto (mismo identificador que usa el front)
    name: str
    brand: str
    unit_price: float
    qty: int
    image: str | None = None

    @classmethod
    def from_model(cls, item: OrderItem) -> "OrderItemOut":
        product = item.product
        return cls(
            id=product.slug if product else item.product_id,
            name=item.name_snapshot,
            brand=item.brand_snapshot,
            unit_price=float(item.unit_price),
            qty=item.qty,
            image=product.image if product else None,
        )


class OrderOut(BaseModel):
    id: str
    number: str
    status: str
    subtotal: float
    discount_code: str | None = None
    discount_amount: float
    shipping_cost: float
    tax: float
    total: float
    shipping_method: str
    shipping_address: dict | None = None
    tracking_number: str | None = None
    tracking_carrier: str | None = None
    tracking_url: str | None = None
    created_at: datetime
    items: list[OrderItemOut]

    @classmethod
    def from_model(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            subtotal=float(order.subtotal),
            discount_code=order.discount_code,
            discount_amount=float(order.discount_amount),
            shipping_cost=float(order.shipping_cost),
            tax=float(order.tax),
            total=float(order.total),
            shipping_method=order.shipping_method,
            shipping_address=order.shipping_address,
            tracking_number=order.tracking_number,
            tracking_carrier=order.tracking_carrier,
            tracking_url=order.tracking_url,
            created_at=order.created_at,
            items=[OrderItemOut.from_model(i) for i in order.items],
        )


class OrderAdminOut(OrderOut):
    user: UserOut

    @classmethod
    def from_model(cls, order: Order) -> "OrderAdminOut":
        base = OrderOut.from_model(order)
        return cls(**base.model_dump(), user=UserOut.model_validate(order.user))


class OrderStatusIn(BaseModel):
    status: Literal["paid", "shipped", "delivered", "canceled"]


class OrderTrackingIn(BaseModel):
    tracking_number: str = Field(min_length=3, max_length=100)
    tracking_carrier: str | None = Field(default=None, max_length=60)
    tracking_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")
