from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cart import CartItemIn

ShippingMethod = Literal["standard", "eco"]


class ShippingQuoteIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1, max_length=50)
    method: ShippingMethod = "standard"


class ShippingQuoteOut(BaseModel):
    subtotal: float
    shipping: float
    free_shipping_threshold: float
    method: str
    total_estimate: float
