from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import Order, OrderItem, Product, User


def _orden(db, user, number, slug, qty, status, dias_atras=0, total=None):
    producto = db.query(Product).filter_by(slug=slug).one()
    subtotal = producto.price * qty
    order = Order(
        number=number,
        user_id=user.id,
        status=status,
        subtotal=subtotal,
        shipping_cost=Decimal("0.00"),
        tax=Decimal("0.00"),
        total=total if total is not None else subtotal,
        shipping_method="standard",
        created_at=datetime.now(UTC) - timedelta(days=dias_atras),
        items=[
            OrderItem(
                product_id=producto.id,
                name_snapshot=producto.name,
                brand_snapshot=producto.brand,
                unit_price=producto.price,
                qty=qty,
            )
        ],
    )
    db.add(order)
    db.commit()
    return order


def test_metrics_prohibido_para_customer(client, products, customer_headers):
    assert client.get("/admin/metrics", headers=customer_headers).status_code == 403


def test_metrics_solo_cuenta_pedidos_pagados_en_ventana(
    client, products, customer_headers, admin_headers, db
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()

    _orden(db, yo, "AX-1001", "khamrah", 2, "paid")  # 170 — cuenta
    _orden(db, yo, "AX-1002", "9pm", 1, "shipped", dias_atras=3)  # 80 — cuenta
    _orden(db, yo, "AX-1003", "naxos", 1, "delivered", dias_atras=10)  # 70 — cuenta
    _orden(db, yo, "AX-1004", "althair", 1, "pending")  # NO cuenta
    _orden(db, yo, "AX-1005", "althair", 1, "canceled")  # NO cuenta
    _orden(db, yo, "AX-1006", "sauvage-edp", 1, "paid", dias_atras=45)  # fuera de ventana

    res = client.get("/admin/metrics?days=30", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["revenue_total"] == 320.0  # 170 + 80 + 70
    assert data["orders_count"] == 3
    assert data["aov"] == 106.67

    assert len(data["revenue_by_day"]) == 30
    hoy = data["revenue_by_day"][-1]
    assert hoy["revenue"] == 170.0
    assert hoy["orders"] == 1

    top = data["top_products"]
    assert top[0]["slug"] == "khamrah"
    assert top[0]["units"] == 2
    assert top[0]["revenue"] == 170.0
    assert {p["slug"] for p in top} == {"khamrah", "9pm", "naxos"}

    # cliente registrado por el fixture dentro de la ventana
    assert data["new_customers"] == 1


def test_metrics_low_stock(client, products, admin_headers, db):
    khamrah = db.query(Product).filter_by(slug="khamrah").one()
    khamrah.stock = 2
    naxos = db.query(Product).filter_by(slug="naxos").one()
    naxos.stock = 0
    naxos.active = False  # inactivo: no debe aparecer
    db.commit()

    data = client.get("/admin/metrics", headers=admin_headers).json()
    assert data["low_stock"] == [{"slug": "khamrah", "name": "Khamrah", "stock": 2}]


def test_metrics_sin_pedidos(client, products, admin_headers):
    data = client.get("/admin/metrics?days=7", headers=admin_headers).json()
    assert data["revenue_total"] == 0
    assert data["orders_count"] == 0
    assert data["aov"] == 0
    assert data["top_products"] == []
    assert len(data["revenue_by_day"]) == 7
