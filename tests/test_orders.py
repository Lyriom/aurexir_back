from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import InventoryMovement, Order, OrderItem, Product, User
from app.services import stripe_service
from tests.stripe_utils import checkout_completed_event, fake_session, sign_payload


def _crear_orden(db, user, number, status="paid", minutos_atras=0):
    khamrah = db.query(Product).filter_by(slug="khamrah").one()
    order = Order(
        number=number,
        user_id=user.id,
        status=status,
        subtotal=Decimal("170.00"),
        shipping_cost=Decimal("6.95"),
        tax=Decimal("0.00"),
        total=Decimal("176.95"),
        shipping_method="standard",
        created_at=datetime.now(UTC) - timedelta(minutes=minutos_atras),
        items=[
            OrderItem(
                product_id=khamrah.id,
                name_snapshot=khamrah.name,
                brand_snapshot=khamrah.brand,
                unit_price=khamrah.price,
                qty=2,
            )
        ],
    )
    db.add(order)
    db.commit()
    return order


def test_orders_mine_requiere_sesion(client, products):
    assert client.get("/orders/mine").status_code == 401


def test_orders_mine_solo_del_usuario_y_mas_reciente_primero(
    client, products, customer_headers, db
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    otro = User(email="otro@test.com", name="Otro", password_hash="x", role="customer")
    db.add(otro)
    db.commit()

    _crear_orden(db, yo, "AX-1001", minutos_atras=60)
    _crear_orden(db, yo, "AX-1002", minutos_atras=5)
    _crear_orden(db, otro, "AX-1003")

    res = client.get("/orders/mine", headers=customer_headers)
    assert res.status_code == 200
    data = res.json()
    assert [o["number"] for o in data] == ["AX-1002", "AX-1001"]
    item = data[0]["items"][0]
    assert item["id"] == "khamrah"
    assert item["name"] == "Khamrah"
    assert item["unit_price"] == 85
    assert item["qty"] == 2


def test_admin_orders_prohibido_para_customer(client, products, customer_headers):
    assert client.get("/admin/orders", headers=customer_headers).status_code == 403


def test_admin_orders_lista_y_filtra(client, products, customer_headers, admin_headers, db):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    _crear_orden(db, yo, "AX-1001", status="paid")
    _crear_orden(db, yo, "AX-1002", status="pending")

    todos = client.get("/admin/orders", headers=admin_headers).json()
    assert len(todos) == 2
    assert todos[0]["user"]["email"] == "cliente@test.com"

    pagados = client.get("/admin/orders?status=paid", headers=admin_headers).json()
    assert [o["number"] for o in pagados] == ["AX-1001"]

    assert client.get("/admin/orders?status=nada", headers=admin_headers).status_code == 422


def test_transicion_valida_paid_shipped_delivered(
    client, products, customer_headers, admin_headers, db
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-1001", status="paid")

    res = client.patch(
        f"/admin/orders/{orden.id}", json={"status": "shipped"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["status"] == "shipped"

    res = client.patch(
        f"/admin/orders/{orden.id}", json={"status": "delivered"}, headers=admin_headers
    )
    assert res.json()["status"] == "delivered"


def test_transicion_invalida_da_409(client, products, customer_headers, admin_headers, db):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-1001", status="pending")

    res = client.patch(
        f"/admin/orders/{orden.id}", json={"status": "shipped"}, headers=admin_headers
    )
    assert res.status_code == 409

    entregada = _crear_orden(db, yo, "AX-1002", status="delivered")
    res = client.patch(
        f"/admin/orders/{entregada.id}", json={"status": "canceled"}, headers=admin_headers
    )
    assert res.status_code == 409


def test_cancelar_orden_pagada_repone_stock(
    client, products, customer_headers, admin_headers, db, monkeypatch
):
    # Flujo real: checkout → webhook (descuenta stock) → cancelación admin (repone)
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    body = {
        "items": [{"id": "khamrah", "qty": 3}],
        "shipping_method": "standard",
        "success_url": "http://localhost:5173/?checkout=success",
        "cancel_url": "http://localhost:5173/?checkout=cancel",
    }
    assert client.post("/checkout/session", json=body, headers=customer_headers).status_code == 200

    payload = checkout_completed_event()
    client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": sign_payload(payload)}
    )
    assert db.query(Product).filter_by(slug="khamrah").one().stock == 7

    orden = db.query(Order).one()
    res = client.patch(
        f"/admin/orders/{orden.id}", json={"status": "canceled"}, headers=admin_headers
    )
    assert res.status_code == 200

    assert db.query(Product).filter_by(slug="khamrah").one().stock == 10
    reposicion = db.query(InventoryMovement).filter_by(reason="cancel", order_id=orden.id).one()
    assert reposicion.delta == 3


def test_cancelar_orden_pendiente_no_toca_stock(
    client, products, customer_headers, admin_headers, db
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-1001", status="pending")

    res = client.patch(
        f"/admin/orders/{orden.id}", json={"status": "canceled"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert db.query(Product).filter_by(slug="khamrah").one().stock == 10
    assert db.query(InventoryMovement).count() == 0
