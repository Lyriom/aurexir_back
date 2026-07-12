"""Inventario: TODO cambio de stock pasa por aquí y deja InventoryMovement."""

import logging

from sqlalchemy.orm import Session

from app.models import InventoryMovement, Order, Product

logger = logging.getLogger(__name__)


def apply_movement(
    db: Session, product: Product, delta: int, reason: str, order_id: str | None = None
) -> InventoryMovement | None:
    """Aplica un delta al stock (sin dejarlo negativo) y registra el movimiento.

    Devuelve el movimiento con el delta REALMENTE aplicado, o None si no hubo
    cambio (p. ej. venta con stock ya agotado por una carrera).
    """
    applied = delta
    if product.stock + delta < 0:
        logger.warning(
            "Stock insuficiente en %s: delta %s con stock %s; se ajusta a 0",
            product.slug,
            delta,
            product.stock,
        )
        applied = -product.stock
    if applied == 0:
        return None
    product.stock += applied
    movement = InventoryMovement(
        product_id=product.id, delta=applied, reason=reason, order_id=order_id
    )
    db.add(movement)
    return movement


def deduct_for_order(db: Session, order: Order) -> None:
    """Descuenta el stock de una orden pagada (movimiento `sale`)."""
    for item in order.items:
        product = db.get(Product, item.product_id)
        if product is not None:
            apply_movement(db, product, -item.qty, "sale", order.id)


def restock_for_order(db: Session, order: Order) -> None:
    """Repone el stock de una orden pagada que se cancela (movimiento `cancel`)."""
    for item in order.items:
        product = db.get(Product, item.product_id)
        if product is not None:
            apply_movement(db, product, item.qty, "cancel", order.id)
