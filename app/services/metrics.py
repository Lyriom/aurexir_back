"""Métricas de ventas para el panel de admin.

Solo cuentan los pedidos con pago confirmado (paid/shipped/delivered) dentro
de la ventana. La agregación por día se hace en Python: la ventana es acotada
(≤ 365 días) y así el cálculo es idéntico en PostgreSQL y SQLite.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import PAID_STATUSES, Order, OrderItem, Product, User

TWO_PLACES = Decimal("0.01")


def compute_metrics(db: Session, days: int) -> dict:
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    orders = db.scalars(
        select(Order)
        .where(Order.status.in_(PAID_STATUSES), Order.created_at >= since)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
    ).all()

    revenue_total = sum((o.total for o in orders), Decimal("0"))
    orders_count = len(orders)
    aov = (revenue_total / orders_count).quantize(TWO_PLACES) if orders_count else Decimal("0")

    # Ventana completa día a día (con ceros) para graficar directo en el front.
    by_day: dict[str, dict] = {}
    for offset in range(days - 1, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        by_day[day] = {"date": day, "revenue": 0.0, "orders": 0}
    for order in orders:
        created = order.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        day = created.astimezone(UTC).date().isoformat()
        if day in by_day:
            by_day[day]["revenue"] = round(by_day[day]["revenue"] + float(order.total), 2)
            by_day[day]["orders"] += 1

    # Top productos por unidades vendidas (con ingresos al precio de compra).
    top: dict[str, dict] = {}
    for order in orders:
        for item in order.items:
            slug = item.product.slug if item.product else item.product_id
            entry = top.setdefault(
                slug, {"slug": slug, "name": item.name_snapshot, "units": 0, "revenue": 0.0}
            )
            entry["units"] += item.qty
            entry["revenue"] = round(entry["revenue"] + float(item.unit_price) * item.qty, 2)
    top_products = sorted(top.values(), key=lambda e: (-e["units"], -e["revenue"]))[:5]

    low_stock = [
        {"slug": p.slug, "name": p.name, "stock": p.stock}
        for p in db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.stock <= get_settings().low_stock_threshold)
            .order_by(Product.stock, Product.slug)
        ).all()
    ]

    new_customers = len(
        db.scalars(select(User.id).where(User.role == "customer", User.created_at >= since)).all()
    )

    return {
        "revenue_total": float(revenue_total),
        "orders_count": orders_count,
        "aov": float(aov),
        "revenue_by_day": list(by_day.values()),
        "top_products": top_products,
        "low_stock": low_stock,
        "new_customers": new_customers,
    }
