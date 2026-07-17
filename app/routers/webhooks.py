"""Webhook de Stripe: única vía por la que un pedido pasa a `paid`.

Probar en local con:
    stripe listen --forward-to localhost:8000/webhooks/stripe
"""

import json
import logging
from decimal import Decimal
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import DiscountCode, Order
from app.models.base import utcnow
from app.services import email as email_service
from app.services.inventory import deduct_for_order

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

DbDep = Annotated[Session, Depends(get_db)]


def _find_order(db: Session, session: dict) -> Order | None:
    order = db.scalar(select(Order).where(Order.stripe_session_id == session.get("id")))
    if order is None:
        order_id = (session.get("metadata") or {}).get("order_id")
        if order_id:
            order = db.get(Order, order_id)
    return order


def _handle_completed(db: Session, session: dict) -> None:
    order = _find_order(db, session)
    if order is None:
        logger.warning("checkout.session.completed sin orden asociada: %s", session.get("id"))
        return
    if order.status != "pending":  # reintentos del webhook: idempotente
        return

    order.status = "paid"
    order.stripe_payment_intent = session.get("payment_intent")

    total_details = session.get("total_details") or {}
    order.tax = Decimal(total_details.get("amount_tax", 0)) / 100
    if session.get("amount_total") is not None:
        order.total = Decimal(session["amount_total"]) / 100

    shipping_details = session.get("shipping_details") or (
        session.get("collected_information") or {}
    ).get("shipping_details")
    if shipping_details:
        order.shipping_address = shipping_details

    deduct_for_order(db, order)

    # El código de descuento se consume solo con el pago confirmado.
    if order.discount_code:
        discount = db.scalar(
            select(DiscountCode).where(DiscountCode.code == order.discount_code)
        )
        if discount is not None and discount.used_at is None:
            discount.used_at = utcnow()
            discount.order_id = order.id

    # Confirmación de compra (best-effort: un fallo de email no revierte el pago).
    email_service.send_order_confirmation(order.user.email, order)


def _handle_expired(db: Session, session: dict) -> None:
    order = _find_order(db, session)
    if order is not None and order.status == "pending":
        order.status = "canceled"


@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbDep) -> dict[str, bool]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        # Verificación de firma equivalente a stripe.Webhook.construct_event,
        # pero trabajando con dicts planos en lugar de StripeObject.
        stripe.WebhookSignature.verify_header(
            payload.decode("utf-8"),
            signature,
            get_settings().stripe_webhook_secret,
            stripe.Webhook.DEFAULT_TOLERANCE,
        )
        event = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Firma de webhook inválida"
        ) from None

    session = event["data"]["object"]
    if event["type"] == "checkout.session.completed":
        _handle_completed(db, session)
    elif event["type"] == "checkout.session.expired":
        _handle_expired(db, session)

    db.commit()
    return {"received": True}
