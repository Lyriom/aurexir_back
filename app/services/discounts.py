"""Códigos de descuento del newsletter: generación y validación."""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DiscountCode

# Sin caracteres ambiguos (0/O, 1/I/L) para que el código se teclee sin errores.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _random_code(percent: int) -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return f"AURX{percent}-{suffix}"


def get_or_create_for_email(db: Session, email: str) -> DiscountCode:
    """Devuelve el código del suscriptor; solo se crea uno por email (usado o no)."""
    existing = db.scalar(select(DiscountCode).where(DiscountCode.email == email))
    if existing is not None:
        return existing

    percent = get_settings().newsletter_discount_percent
    code = _random_code(percent)
    while db.scalar(select(DiscountCode).where(DiscountCode.code == code)):
        code = _random_code(percent)

    discount = DiscountCode(code=code, email=email, percent=percent)
    db.add(discount)
    return discount


def find_valid(db: Session, code: str) -> DiscountCode | None:
    """Código existente y aún sin usar, o None."""
    normalized = code.strip().upper()
    discount = db.scalar(select(DiscountCode).where(DiscountCode.code == normalized))
    if discount is None or discount.used_at is not None:
        return None
    return discount
