"""Regla de envío (solo EE. UU.). La usan el quote Y la Checkout Session."""

from decimal import Decimal

from app.config import get_settings

TWO_PLACES = Decimal("0.01")


def compute_shipping(subtotal: Decimal, method: str) -> Decimal:
    """Envío gratis si el subtotal alcanza el umbral; si no, tarifa plana por método."""
    settings = get_settings()
    if subtotal >= settings.free_shipping_threshold:
        return Decimal("0.00")
    rate = settings.shipping_standard if method == "standard" else settings.shipping_express
    return rate.quantize(TWO_PLACES)
