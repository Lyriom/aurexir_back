from pydantic import BaseModel, Field

from app.schemas.cart import CartItemIn
from app.schemas.shipping import ShippingMethod


class CheckoutIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    shipping_method: ShippingMethod = "standard"
    success_url: str = Field(pattern=r"^https?://")
    cancel_url: str = Field(pattern=r"^https?://")


class CheckoutOut(BaseModel):
    checkout_url: str
