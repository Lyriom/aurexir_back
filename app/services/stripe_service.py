"""Integración con Stripe Checkout (modo test).

Los precios salen de la base de datos y van a Stripe en centavos. El envío se
calcula con services/shipping.py (la misma regla que /shipping/quote) y viaja
como shipping_option de monto fijo.
"""

import logging
from decimal import Decimal

import stripe

from app.config import get_settings
from app.models import Order, Product

logger = logging.getLogger(__name__)

SHIPPING_LABELS = {"standard": "Standard (3-5 días)", "express": "Express (1-2 días)"}


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def create_checkout_session(
    *,
    order: Order,
    resolved_items: list[tuple[Product, int]],
    shipping_cost: Decimal,
    success_url: str,
    cancel_url: str,
    customer_email: str,
) -> stripe.checkout.Session:
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key

    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"{product.brand} — {product.name}"},
                "unit_amount": to_cents(product.price),
                "tax_behavior": "exclusive",
            },
            "quantity": qty,
        }
        for product, qty in resolved_items
    ]

    params: dict = {
        "mode": "payment",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_email": customer_email,
        "client_reference_id": order.id,
        "metadata": {"order_id": order.id, "order_number": order.number},
        "shipping_address_collection": {"allowed_countries": ["US"]},
        "shipping_options": [
            {
                "shipping_rate_data": {
                    "type": "fixed_amount",
                    "display_name": SHIPPING_LABELS[order.shipping_method],
                    "fixed_amount": {"amount": to_cents(shipping_cost), "currency": "usd"},
                    "tax_behavior": "exclusive",
                }
            }
        ],
        # Stripe Tax calcula el sales tax por estado (registro en NY).
        "automatic_tax": {"enabled": True},
    }

    try:
        return stripe.checkout.Session.create(**params)
    except stripe.StripeError as exc:
        # TODO: si la cuenta no tiene Stripe Tax activo, la sesión se crea sin
        # impuestos y Order.tax queda en 0. Activar Stripe Tax en el dashboard
        # (registro en NY) para cobrar sales tax.
        if "tax" in str(exc).lower():
            logger.warning("Stripe Tax no disponible; se reintenta sin automatic_tax: %s", exc)
            params.pop("automatic_tax")
            return stripe.checkout.Session.create(**params)
        raise
