from app.models import InventoryMovement, Product

NUEVO = {
    "slug": "test-nuevo",
    "name": "Test Nuevo",
    "brand": "Marca",
    "category": "night",
    "price": 99.5,
    "oldPrice": 120,
    "image": "/perfumes/test-nuevo-1.webp",
    "gallery": ["/perfumes/test-nuevo-1.webp"],
    "desc": {"en": "New tester", "es": "Probador nuevo"},
    "stock": 15,
}


def test_admin_products_prohibido_para_customer(client, products, customer_headers):
    assert client.get("/admin/products", headers=customer_headers).status_code == 403
    assert client.post("/admin/products", json=NUEVO, headers=customer_headers).status_code == 403


def test_admin_products_incluye_inactivos(client, products, admin_headers, db):
    p = db.query(Product).filter_by(slug="naxos").one()
    p.active = False
    db.commit()

    data = client.get("/admin/products", headers=admin_headers).json()
    assert len(data) == 20  # el público vería 19
    naxos = next(x for x in data if x["id"] == "naxos")
    assert naxos["active"] is False
    assert naxos["uuid"]


def test_crear_producto_con_stock_inicial_auditado(client, admin_headers, db):
    res = client.post("/admin/products", json=NUEVO, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "test-nuevo"
    assert data["price"] == 99.5
    assert data["stock"] == 15

    movimiento = db.query(InventoryMovement).one()
    assert movimiento.delta == 15
    assert movimiento.reason == "restock"

    # visible en el catálogo público
    assert client.get("/products/test-nuevo").status_code == 200


def test_crear_slug_duplicado_da_409(client, products, admin_headers):
    body = dict(NUEVO, slug="khamrah")
    assert client.post("/admin/products", json=body, headers=admin_headers).status_code == 409


def test_editar_precio_y_desactivar_por_slug(client, products, admin_headers, db):
    res = client.patch(
        "/admin/products/khamrah",
        json={"price": 95, "active": False},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["price"] == 95
    assert res.json()["active"] is False

    # desactivado → fuera del catálogo público
    assert client.get("/products/khamrah").status_code == 404


def test_editar_por_uuid_interno(client, products, admin_headers, db):
    uuid = db.query(Product).filter_by(slug="9pm").one().id
    res = client.patch(f"/admin/products/{uuid}", json={"isBest": False}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["isBest"] is False


def test_editar_producto_inexistente_da_404(client, products, admin_headers):
    res = client.patch("/admin/products/fantasma", json={"price": 1}, headers=admin_headers)
    assert res.status_code == 404


def test_actualizar_stock_por_delta(client, products, admin_headers, db):
    # El front manda delta: +15 repone (10 → 25), -20 reduce (25 → 5).
    res = client.patch(
        "/admin/products/khamrah/stock",
        json={"delta": 15, "reason": "restock"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["stock"] == 25

    res = client.patch(
        "/admin/products/khamrah/stock",
        json={"delta": -20, "reason": "manual"},
        headers=admin_headers,
    )
    assert res.json()["stock"] == 5

    deltas = [
        (m.delta, m.reason)
        for m in db.query(InventoryMovement).order_by(InventoryMovement.created_at).all()
    ]
    assert (15, "restock") in deltas
    assert (-20, "manual") in deltas


def test_stock_delta_no_baja_de_cero(client, products, admin_headers, db):
    # Un delta que dejaría el stock negativo se ajusta a 0 (nunca negativo).
    res = client.patch(
        "/admin/products/khamrah/stock",
        json={"delta": -999, "reason": "manual"},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["stock"] == 0


def test_stock_delta_no_entero_da_422(client, products, admin_headers):
    res = client.patch(
        "/admin/products/khamrah/stock",
        json={"delta": "cinco", "reason": "manual"},
        headers=admin_headers,
    )
    assert res.status_code == 422
