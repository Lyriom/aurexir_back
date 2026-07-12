from decimal import Decimal
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order, OrderItem
from app.schemas.checkout import CheckoutIn, CheckoutOut
from app.security import CurrentUser
from app.services import stripe_service
from app.services.cart import cart_subtotal, resolve_items
from app.services.orders import next_order_number
from app.services.shipping import compute_shipping

router = APIRouter(prefix="/checkout", tags=["checkout"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/session", response_model=CheckoutOut)
def create_checkout_session(payload: CheckoutIn, user: CurrentUser, db: DbDep) -> CheckoutOut:
    resolved = resolve_items(db, payload.items)

    # El stock se valida aquí pero se descuenta SOLO cuando el webhook confirma el pago.
    insufficient = [
        {"id": product.slug, "requested": qty, "available": product.stock}
        for product, qty in resolved
        if product.stock < qty
    ]
    if insufficient:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"insufficient_stock": insufficient},
        )

    subtotal = cart_subtotal(resolved)
    shipping_cost = compute_shipping(subtotal, payload.shipping_method)

    order = Order(
        number=next_order_number(db),
        user_id=user.id,
        status="pending",
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        tax=Decimal("0.00"),  # el impuesto final lo reporta el webhook (Stripe Tax)
        total=subtotal + shipping_cost,
        shipping_method=payload.shipping_method,
        items=[
            OrderItem(
                product_id=product.id,
                name_snapshot=product.name,
                brand_snapshot=product.brand,
                unit_price=product.price,
                qty=qty,
            )
            for product, qty in resolved
        ],
    )
    db.add(order)
    db.flush()

    try:
        session = stripe_service.create_checkout_session(
            order=order,
            resolved_items=resolved,
            shipping_cost=shipping_cost,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            customer_email=user.email,
        )
    except stripe.StripeError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo iniciar el pago con Stripe; inténtalo de nuevo",
        ) from None

    order.stripe_session_id = session.id
    db.commit()
    return CheckoutOut(checkout_url=session.url)
