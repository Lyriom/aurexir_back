"""Flujo completo del 15% del newsletter: alta → email con código → checkout → webhook."""

from decimal import Decimal

from app.models import DiscountCode, Order
from app.routers import newsletter as newsletter_router
from app.services import discounts, stripe_service
from tests.stripe_utils import checkout_completed_event, fake_session, sign_payload

CHECKOUT_BODY = {
    "items": [{"id": "khamrah", "qty": 2}, {"id": "9pm", "qty": 1}],
    "shipping_method": "standard",
    "success_url": "http://localhost:5173/?checkout=success",
    "cancel_url": "http://localhost:5173/?checkout=cancel",
}


def _subscribe(client, monkeypatch, email="promo@test.com", locale="es"):
    """Alta en el newsletter capturando el email que se habría enviado."""
    enviados = []

    def fake_send(to_email, code, percent, locale="en"):
        enviados.append({"to": to_email, "code": code, "percent": percent, "locale": locale})
        return True

    monkeypatch.setattr(newsletter_router.email_service, "send_discount_email", fake_send)
    res = client.post("/newsletter", json={"email": email, "locale": locale})
    return res, enviados


def test_alta_crea_codigo_y_lo_envia(client, db, monkeypatch):
    res, enviados = _subscribe(client, monkeypatch)
    assert res.status_code == 201
    assert res.json() == {"status": "subscribed", "discount_email_sent": True}

    codigo = db.query(DiscountCode).one()
    assert codigo.email == "promo@test.com"
    assert codigo.percent == 15
    assert codigo.used_at is None
    assert codigo.code.startswith("AURX15-")

    assert enviados == [
        {"to": "promo@test.com", "code": codigo.code, "percent": 15, "locale": "es"}
    ]


def test_alta_repetida_reenvia_el_mismo_codigo(client, db, monkeypatch):
    _subscribe(client, monkeypatch)
    res, enviados = _subscribe(client, monkeypatch)
    assert res.status_code == 200
    assert res.json()["status"] == "already_subscribed"
    assert db.query(DiscountCode).count() == 1
    assert enviados[0]["code"] == db.query(DiscountCode).one().code


def test_fallo_de_resend_no_rompe_el_alta(client, db):
    # Sin RESEND_API_KEY (conftest) el envío es no-op y devuelve False.
    res = client.post("/newsletter", json={"email": "promo@test.com", "locale": "en"})
    assert res.status_code == 201
    assert res.json() == {"status": "subscribed", "discount_email_sent": False}
    assert db.query(DiscountCode).count() == 1


def test_validate_codigo_valido_invalido_y_usado(client, db, monkeypatch):
    _subscribe(client, monkeypatch)
    codigo = db.query(DiscountCode).one()

    ok = client.post("/discounts/validate", json={"code": codigo.code.lower()})
    assert ok.status_code == 200
    assert ok.json() == {"valid": True, "code": codigo.code, "percent": 15}

    # Código inexistente: 200 con el código (normalizado) y percent 0, nunca 4xx.
    mal = client.post("/discounts/validate", json={"code": "aurx15-noexiste"})
    assert mal.status_code == 200
    assert mal.json() == {"valid": False, "code": "AURX15-NOEXISTE", "percent": 0}

    codigo.used_at = codigo.created_at
    db.commit()
    usado = client.post("/discounts/validate", json={"code": codigo.code})
    assert usado.json() == {"valid": False, "code": codigo.code, "percent": 0}


def test_checkout_aplica_15_y_manda_cupon_a_stripe(
    client, products, customer_headers, db, monkeypatch
):
    _subscribe(client, monkeypatch)
    codigo = db.query(DiscountCode).one()

    capturado = {}
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session,
        "create",
        lambda **params: capturado.update(params) or fake_session(),
    )
    monkeypatch.setattr(
        stripe_service.stripe.Coupon,
        "create",
        lambda **kw: type("C", (), {"id": "coup_test_15"})(),
    )

    body = dict(CHECKOUT_BODY, discount_code=codigo.code)
    res = client.post("/checkout/session", json=body, headers=customer_headers)
    assert res.status_code == 200

    order = db.query(Order).one()
    # khamrah 85*2 + 9pm 80 = 250; 15% = 37.50; envío gratis por subtotal >= 200
    assert float(order.subtotal) == 250.00
    assert order.discount_code == codigo.code
    assert float(order.discount_amount) == 37.50
    assert float(order.total) == 212.50
    assert capturado["discounts"] == [{"coupon": "coup_test_15"}]

    # Crear la sesión NO consume el código todavía
    assert db.query(DiscountCode).one().used_at is None


def test_checkout_con_codigo_invalido_da_409(client, products, customer_headers, db):
    body = dict(CHECKOUT_BODY, discount_code="AURX15-NOEXISTE")
    res = client.post("/checkout/session", json=body, headers=customer_headers)
    assert res.status_code == 409
    assert "descuento" in res.json()["detail"].lower()
    assert db.query(Order).count() == 0


def test_webhook_consume_el_codigo(client, products, customer_headers, db, monkeypatch):
    _subscribe(client, monkeypatch)
    codigo = db.query(DiscountCode).one()

    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    monkeypatch.setattr(
        stripe_service.stripe.Coupon, "create", lambda **kw: type("C", (), {"id": "coup_x"})()
    )
    body = dict(CHECKOUT_BODY, discount_code=codigo.code)
    assert (
        client.post("/checkout/session", json=body, headers=customer_headers).status_code == 200
    )

    payload = checkout_completed_event(amount_total=21250)
    res = client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": sign_payload(payload)}
    )
    assert res.status_code == 200

    order = db.query(Order).one()
    assert order.status == "paid"
    assert order.total == Decimal("212.50")

    codigo_db = db.query(DiscountCode).one()
    assert codigo_db.used_at is not None
    assert codigo_db.order_id == order.id

    # Y ya no se puede reutilizar
    res = client.post("/checkout/session", json=body, headers=customer_headers)
    assert res.status_code == 409


def test_codigo_unico_por_email_aunque_este_usado(client, db, monkeypatch):
    _subscribe(client, monkeypatch)
    codigo = db.query(DiscountCode).one()
    codigo.used_at = codigo.created_at
    db.commit()

    res, enviados = _subscribe(client, monkeypatch)
    assert res.status_code == 200
    assert db.query(DiscountCode).count() == 1  # no se regala otro código
    assert enviados == []  # y no se reenvía uno gastado
    assert res.json()["discount_email_sent"] is False


def test_get_or_create_reutiliza_codigo_existente(db):
    a = discounts.get_or_create_for_email(db, "x@test.com")
    db.commit()
    b = discounts.get_or_create_for_email(db, "x@test.com")
    assert a.id == b.id
