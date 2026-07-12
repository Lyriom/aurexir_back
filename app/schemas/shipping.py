from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cart import CartItemIn

ShippingMethod = Literal["standard", "express"]


class ShippingQuoteIn(BaseModel):
    items: list[CartItemIn] = Field(min_length=1)
    zip: str = Field(pattern=r"^\d{5}$", description="ZIP de EE. UU. (5 dígitos)")
    method: ShippingMethod = "standard"


class ShippingQuoteOut(BaseModel):
    subtotal: float
    shipping: float
    free_shipping_threshold: float
    method: str
    total_estimate: float
