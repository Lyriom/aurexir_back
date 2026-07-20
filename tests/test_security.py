"""Pruebas de blindaje: secreto JWT, cabeceras, límites de payload y open redirect."""

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services import stripe_service
from tests.stripe_utils import fake_session

CHECKOUT_BODY = {
    "items": [{"id": "khamrah", "qty": 1}],
    "shipping_method": "standard",
    "success_url": "http://localhost:5173/checkout/success",
    "cancel_url": "http://localhost:5173/checkout/cancel",
}


# ---- Secreto JWT ----


@pytest.mark.parametrize("bad", ["dev-secret-cambia-esto", "short", "cambia-esto", "x" * 31])
def test_jwt_secret_debil_no_arranca(bad):
    with pytest.raises(ValidationError):
        Settings(jwt_secret=bad)


def test_jwt_secret_fuerte_es_valido():
    s = Settings(jwt_secret="x" * 32)
    assert s.jwt_secret == "x" * 32


# ---- Cabeceras de seguridad ----


def test_respuestas_traen_cabeceras_de_seguridad(client):
    res = client.get("/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert "max-age=" in res.headers["strict-transport-security"]
    assert res.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"


# ---- Límite de tamaño de cuerpo ----


def test_cuerpo_gigante_da_413(client):
    huge = "x" * 1_100_000  # > 1 MB
    res = client.post(
        "/newsletter",
        content=f'{{"email":"a@b.com","locale":"es","junk":"{huge}"}}',
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 413


# ---- Tope de items (anti-DoS) ----


def test_quote_con_demasiados_items_da_422(client, products):
    body = {"items": [{"id": "khamrah", "qty": 1}] * 51, "method": "standard"}
    assert client.post("/shipping/quote", json=body).status_code == 422


def test_checkout_con_demasiados_items_da_422(client, products, customer_headers):
    body = dict(CHECKOUT_BODY, items=[{"id": "khamrah", "qty": 1}] * 51)
    assert client.post("/checkout/session", json=body, headers=customer_headers).status_code == 422


# ---- Open redirect en checkout ----


def test_checkout_url_de_retorno_externa_da_422(client, products, customer_headers, db):
    from app.models import Order

    body = dict(CHECKOUT_BODY, success_url="https://evil.example.com/phish")
    res = client.post("/checkout/session", json=body, headers=customer_headers)
    assert res.status_code == 422
    assert db.query(Order).count() == 0  # no se creó ninguna orden


def test_checkout_url_de_retorno_propia_pasa(client, products, customer_headers, monkeypatch):
    monkeypatch.setattr(
        stripe_service.stripe.checkout.Session, "create", lambda **kw: fake_session()
    )
    res = client.post("/checkout/session", json=CHECKOUT_BODY, headers=customer_headers)
    assert res.status_code == 200
