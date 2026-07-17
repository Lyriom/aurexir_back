"""Confirmación de compra (webhook) y tracking subido por el admin."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import Order, OrderItem, Product, User
from app.routers import admin as admin_router
from app.routers import webhooks as webhooks_router
from app.services import stripe_service
from tests.stripe_utils import checkout_completed_event, fake_session, sign_payload

CHECKOUT_BODY = {
    "items": [{"id": "khamrah", "qty": 2}],
    "shipping_method": "standard",
    "success_url": "http://localhost:5173/?checkout=success",
    "cancel_url": "http://localhost:5173/?checkout=cancel",
}


def _crear_orden(db, user, number, status="paid"):
    khamrah = db.query(Product).filter_by(slug="khamrah").one()
    order = Order(
        number=number,
        user_id=user.id,
        status=status,
        subtotal=Decimal("170.00"),
        shipping_cost=Decimal("20.00"),
        tax=Decimal("0.00"),
        total=Decimal("190.00"),
        shipping_method="standard",
        locale="es",
        created_at=datetime.now(UTC) - timedelta(minutes=1),
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


# ---- Confirmación de compra al confirmar el pago ----


def test_webhook_envia_confirmacion_de_compra(
    client, products, customer_headers, db, monkeypatch
):
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    body = dict(CHECKOUT_BODY, locale="es")
    assert client.post("/checkout/session", json=body, headers=customer_headers).status_code == 200

    enviados = []
    monkeypatch.setattr(
        webhooks_router.email_service,
        "send_order_confirmation",
        lambda to, order: enviados.append((to, order.number, order.locale)) or True,
    )

    payload = checkout_completed_event(amount_total=19000)
    res = client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": sign_payload(payload)}
    )
    assert res.status_code == 200

    orden = db.query(Order).one()
    assert orden.status == "paid"
    assert orden.locale == "es"
    assert enviados == [("cliente@test.com", orden.number, "es")]


def test_confirmacion_no_rompe_el_webhook_si_email_falla(
    client, products, customer_headers, db, monkeypatch
):
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    assert (
        client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers).status_code
        == 200
    )
    # Sin RESEND_API_KEY (conftest) el envío real es no-op → no lanza y devuelve False.
    payload = checkout_completed_event()
    res = client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": sign_payload(payload)}
    )
    assert res.status_code == 200
    assert db.query(Order).one().status == "paid"


# ---- Tracking subido por el admin ----


def test_set_tracking_envia_correo_y_pasa_a_shipped(
    client, products, customer_headers, admin_headers, db, monkeypatch
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-2001", status="paid")

    enviados = []
    monkeypatch.setattr(
        admin_router.email_service,
        "send_tracking_email",
        lambda to, order: enviados.append((to, order.tracking_number)) or True,
    )

    res = client.patch(
        f"/admin/orders/{orden.id}/tracking",
        json={
            "tracking_number": "1Z999AA10123456784",
            "tracking_carrier": "UPS",
            "tracking_url": "https://www.ups.com/track?tracknum=1Z999AA10123456784",
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "shipped"
    assert data["tracking_number"] == "1Z999AA10123456784"
    assert data["tracking_carrier"] == "UPS"

    db.refresh(orden)
    assert orden.status == "shipped"
    assert enviados == [("cliente@test.com", "1Z999AA10123456784")]


def test_set_tracking_sobre_pedido_ya_enviado_actualiza(
    client, products, customer_headers, admin_headers, db, monkeypatch
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-2002", status="shipped")
    monkeypatch.setattr(admin_router.email_service, "send_tracking_email", lambda to, order: True)

    res = client.patch(
        f"/admin/orders/{orden.id}/tracking",
        json={"tracking_number": "NEW123456"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["tracking_number"] == "NEW123456"
    assert res.json()["status"] == "shipped"


def test_set_tracking_sobre_pedido_pendiente_da_409(
    client, products, customer_headers, admin_headers, db
):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-2003", status="pending")
    res = client.patch(
        f"/admin/orders/{orden.id}/tracking",
        json={"tracking_number": "X123456"},
        headers=admin_headers,
    )
    assert res.status_code == 409


def test_set_tracking_pedido_inexistente_da_404(client, products, admin_headers):
    res = client.patch(
        "/admin/orders/no-existe/tracking",
        json={"tracking_number": "X123456"},
        headers=admin_headers,
    )
    assert res.status_code == 404


def test_set_tracking_requiere_admin(client, products, customer_headers, db):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-2004", status="paid")
    res = client.patch(
        f"/admin/orders/{orden.id}/tracking",
        json={"tracking_number": "X123456"},
        headers=customer_headers,
    )
    assert res.status_code == 403


def test_set_tracking_url_invalida_da_422(client, products, customer_headers, admin_headers, db):
    yo = db.query(User).filter_by(email="cliente@test.com").one()
    orden = _crear_orden(db, yo, "AX-2005", status="paid")
    res = client.patch(
        f"/admin/orders/{orden.id}/tracking",
        json={"tracking_number": "X123456", "tracking_url": "no-es-url"},
        headers=admin_headers,
    )
    assert res.status_code == 422
