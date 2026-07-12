"""Utilidades de pedidos."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Order

FIRST_NUMBER = 1001


def next_order_number(db: Session) -> str:
    """Número secuencial legible (AX-1042). La constraint UNIQUE cubre carreras."""
    count = db.scalar(select(func.count()).select_from(Order)) or 0
    n = FIRST_NUMBER + count
    while db.scalar(select(Order.id).where(Order.number == f"AX-{n}")) is not None:
        n += 1
    return f"AX-{n}"
