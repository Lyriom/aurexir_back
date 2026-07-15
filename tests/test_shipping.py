from decimal import Decimal

import pytest

from app.models import Product


@pytest.fixture()
def producto_precio(db):
    """Crea un producto con precio arbitrario y devuelve su slug."""

    def _crear(precio: str, slug: str = "borde") -> str:
        db.add(
            Product(
                slug=slug,
                name="Borde",
                brand="Test",
                category="daily",
                tone="noir",
                price=Decimal(precio),
                image="/perfumes/borde-1.webp",
                gallery=[],
                stock=10,
            )
        )
        db.commit()
        return slug

    return _crear


def test_subtotal_199_99_cobra_envio(client, producto_precio):
    slug = producto_precio("199.99")
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": slug, "qty": 1}], "method": "standard"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["subtotal"] == 199.99
    assert data["shipping"] == 20
    assert data["total_estimate"] == 219.99
    assert data["free_shipping_threshold"] == 200


def test_subtotal_200_envio_gratis(client, producto_precio):
    slug = producto_precio("200.00")
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": slug, "qty": 1}], "method": "standard"},
    )
    data = res.json()
    assert data["shipping"] == 0
    assert data["total_estimate"] == 200


def test_metodo_eco_bajo_el_umbral(client, producto_precio):
    slug = producto_precio("50.00")
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": slug, "qty": 2}], "method": "eco"},
    )
    data = res.json()
    assert data["subtotal"] == 100
    assert data["shipping"] == 30


def test_precios_salen_de_la_db_no_del_cliente(client, products):
    # khamrah (85) x2 + 9pm (80) x1 = 250 → envío gratis
    res = client.post(
        "/shipping/quote",
        json={
            "items": [{"id": "khamrah", "qty": 2}, {"id": "9pm", "qty": 1}],
            "method": "standard",
        },
    )
    data = res.json()
    assert data["subtotal"] == 250
    assert data["shipping"] == 0


def test_metodo_desconocido_da_422(client, products):
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": "khamrah", "qty": 1}], "method": "express"},
    )
    assert res.status_code == 422


def test_qty_cero_da_422(client, products):
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": "khamrah", "qty": 0}], "method": "standard"},
    )
    assert res.status_code == 422


def test_producto_desconocido_da_404(client, products):
    res = client.post(
        "/shipping/quote",
        json={"items": [{"id": "fantasma", "qty": 1}], "method": "standard"},
    )
    assert res.status_code == 404
    assert "fantasma" in res.json()["detail"]
