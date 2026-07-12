from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.shipping import ShippingQuoteIn, ShippingQuoteOut
from app.services.cart import cart_subtotal, resolve_items
from app.services.shipping import compute_shipping

router = APIRouter(prefix="/shipping", tags=["envío"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/quote", response_model=ShippingQuoteOut)
def quote(payload: ShippingQuoteIn, db: DbDep) -> ShippingQuoteOut:
    resolved = resolve_items(db, payload.items)
    subtotal = cart_subtotal(resolved)
    shipping = compute_shipping(subtotal, payload.method)
    return ShippingQuoteOut(
        subtotal=float(subtotal),
        shipping=float(shipping),
        free_shipping_threshold=float(get_settings().free_shipping_threshold),
        method=payload.method,
        total_estimate=float(subtotal + shipping),
    )
