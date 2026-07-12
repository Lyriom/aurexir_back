"""Resolución del carrito contra la base de datos.

El cliente envía solo {id, qty} (id = slug del producto); los precios salen
SIEMPRE de la base de datos. Compartido por /shipping/quote y /checkout/session.
"""

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.schemas.cart import CartItemIn


def resolve_items(db: Session, items: list[CartItemIn]) -> list[tuple[Product, int]]:
    """Devuelve [(producto, qty)] con cantidades de ids duplicados sumadas.

    404 si algún id no corresponde a un producto activo.
    """
    qty_by_slug: dict[str, int] = {}
    for item in items:
        qty_by_slug[item.id] = qty_by_slug.get(item.id, 0) + item.qty

    products = db.scalars(
        select(Product).where(Product.slug.in_(qty_by_slug), Product.active.is_(True))
    ).all()
    by_slug = {p.slug: p for p in products}

    missing = sorted(set(qty_by_slug) - set(by_slug))
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto no encontrado: {', '.join(missing)}",
        )
    return [(by_slug[slug], qty) for slug, qty in qty_by_slug.items()]


def cart_subtotal(resolved: list[tuple[Product, int]]) -> Decimal:
    return sum((product.price * qty for product, qty in resolved), Decimal("0.00"))
