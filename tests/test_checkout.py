from app.models import Order, Product
from app.services import stripe_service
from tests.stripe_utils import fake_session

CHECKOUT_BODY = {
    "items": [{"id": "khamrah", "qty": 2}, {"id": "9pm", "qty": 1}],
    "shipping_method": "standard",
    "success_url": "http://localhost:5173/?checkout=success",
    "cancel_url": "http://localhost:5173/?checkout=cancel",
}


def test_checkout_requiere_sesion(client, products):
    assert client.post("/checkout/session", json=CHECKOUT_BODY).status_code == 401


def test_checkout_crea_orden_pending_con_montos_correctos(
    client, products, customer_headers, db, monkeypatch
):
    capturado = {}

    def fake_create(**params):
        capturado.update(params)
        return fake_session()

    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", fake_create)

    res = client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers)
    assert res.status_code == 200
    assert res.json()["checkout_url"].startswith("https://checkout.stripe.com/")

    order = db.query(Order).one()
    assert order.status == "pending"
    assert order.number.startswith("AX-")
    # khamrah 85*2 + 9pm 80 = 250 → envío gratis
    assert float(order.subtotal) == 250.00
    assert float(order.shipping_cost) == 0.00
    assert float(order.total) == 250.00
    assert order.stripe_session_id == "cs_test_123"
    assert len(order.items) == 2

    # El stock NO se descuenta al crear la sesión
    assert db.query(Product).filter_by(slug="khamrah").one().stock == 10

    # Lo enviado a Stripe: centavos desde la DB y solo EE. UU.
    amounts = {li["price_data"]["unit_amount"] for li in capturado["line_items"]}
    assert amounts == {8500, 8000}
    assert capturado["shipping_address_collection"] == {"allowed_countries": ["US"]}
    assert capturado["automatic_tax"] == {"enabled": True}
    envio = capturado["shipping_options"][0]["shipping_rate_data"]["fixed_amount"]["amount"]
    assert envio == 0


def test_checkout_bajo_umbral_cobra_envio(client, products, customer_headers, db, monkeypatch):
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    body = dict(CHECKOUT_BODY, items=[{"id": "naxos", "qty": 1}], shipping_method="express")
    res = client.post("/checkout/session", json=body, headers=customer_headers)
    assert res.status_code == 200
    order = db.query(Order).one()
    assert float(order.subtotal) == 70.00
    assert float(order.shipping_cost) == 14.95
    assert float(order.total) == 84.95


def test_checkout_sin_stock_da_409_con_detalle(client, products, customer_headers, db):
    khamrah = db.query(Product).filter_by(slug="khamrah").one()
    khamrah.stock = 1
    db.commit()

    res = client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers)
    assert res.status_code == 409
    detalle = res.json()["detail"]["insufficient_stock"]
    assert detalle == [{"id": "khamrah", "requested": 2, "available": 1}]
    # No debe quedar ninguna orden creada
    assert db.query(Order).count() == 0


def test_checkout_producto_inactivo_da_404(client, products, customer_headers, db):
    p = db.query(Product).filter_by(slug="khamrah").one()
    p.active = False
    db.commit()
    res = client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers)
    assert res.status_code == 404
