from datetime import datetime
from typing import Literal

from pydantic import BaseModel

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
    shipping_cost: float
    tax: float
    total: float
    shipping_method: str
    shipping_address: dict | None = None
    created_at: datetime
    items: list[OrderItemOut]

    @classmethod
    def from_model(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            subtotal=float(order.subtotal),
            shipping_cost=float(order.shipping_cost),
            tax=float(order.tax),
            total=float(order.total),
            shipping_method=order.shipping_method,
            shipping_address=order.shipping_address,
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
