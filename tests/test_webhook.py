import pytest

from app.models import InventoryMovement, Order, Product
from app.services import stripe_service
from tests.stripe_utils import (
    checkout_completed_event,
    checkout_expired_event,
    fake_session,
    sign_payload,
)

CHECKOUT_BODY = {
    "items": [{"id": "khamrah", "qty": 2}],
    "shipping_method": "standard",
    "success_url": "http://localhost:5173/?checkout=success",
    "cancel_url": "http://localhost:5173/?checkout=cancel",
}


@pytest.fixture()
def orden_pendiente(client, products, customer_headers, db, monkeypatch):
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    res = client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers)
    assert res.status_code == 200
    return db.query(Order).one()


def test_firma_invalida_da_400(client, orden_pendiente, db):
    payload = checkout_completed_event()
    res = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": "t=1,v1=firmafalsa"},
    )
    assert res.status_code == 400
    db.refresh(orden_pendiente)
    assert orden_pendiente.status == "pending"


def test_sin_cabecera_de_firma_da_400(client, orden_pendiente):
    res = client.post("/webhooks/stripe", content=checkout_completed_event())
    assert res.status_code == 400


def test_completed_marca_paid_y_descuenta_stock(client, orden_pendiente, db):
    # 170 de productos + 14.03 de tax = 18403 centavos
    payload = checkout_completed_event(amount_tax=1403, amount_total=18403)
    res = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": sign_payload(payload)},
    )
    assert res.status_code == 200

    db.refresh(orden_pendiente)
    assert orden_pendiente.status == "paid"
    assert orden_pendiente.stripe_payment_intent == "pi_test_123"
    assert float(orden_pendiente.tax) == 14.03
    assert float(orden_pendiente.total) == 184.03
    assert orden_pendiente.shipping_address["address"]["state"] == "NY"

    khamrah = db.query(Product).filter_by(slug="khamrah").one()
    assert khamrah.stock == 8  # 10 - 2

    movimiento = db.query(InventoryMovement).one()
    assert movimiento.delta == -2
    assert movimiento.reason == "sale"
    assert movimiento.order_id == orden_pendiente.id


def test_webhook_es_idempotente(client, orden_pendiente, db):
    payload = checkout_completed_event()
    headers = {"stripe-signature": sign_payload(payload)}
    assert client.post("/webhooks/stripe", content=payload, headers=headers).status_code == 200
    payload2 = checkout_completed_event()
    assert (
        client.post(
            "/webhooks/stripe",
            content=payload2,
            headers={"stripe-signature": sign_payload(payload2)},
        ).status_code
        == 200
    )

    assert db.query(Product).filter_by(slug="khamrah").one().stock == 8  # una sola vez
    assert db.query(InventoryMovement).count() == 1


def test_expired_cancela_orden_pendiente(client, orden_pendiente, db):
    payload = checkout_expired_event()
    res = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": sign_payload(payload)},
    )
    assert res.status_code == 200
    db.refresh(orden_pendiente)
    assert orden_pendiente.status == "canceled"
    # Nunca se descontó stock, así que no hay movimientos
    assert db.query(InventoryMovement).count() == 0
