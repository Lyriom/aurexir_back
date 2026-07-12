from decimal import Decimal

from app.models import Product


def test_lista_solo_productos_activos_con_forma_del_front(client, products, db):
    # Desactivamos uno para comprobar que no se lista
    naxos = db.query(Product).filter_by(slug="naxos").one()
    naxos.active = False
    db.commit()

    res = client.get("/products")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 19
    assert all(p["id"] != "naxos" for p in data)

    khamrah = next(p for p in data if p["id"] == "khamrah")
    assert khamrah["brand"] == "Lattafa"
    assert khamrah["price"] == 85
    assert khamrah["oldPrice"] == 110
    assert khamrah["isBest"] is True
    assert khamrah["stock"] == 10
    assert khamrah["desc"]["es"].startswith("Dátiles")
    assert khamrah["notes"]["top"]["en"]


def test_detalle_por_slug(client, products):
    res = client.get("/products/althair")
    assert res.status_code == 200
    assert res.json()["brand"] == "Parfums de Marly"
    assert res.json()["tag"] == "niche"


def test_producto_inexistente_da_404(client, products):
    assert client.get("/products/no-existe").status_code == 404


def test_producto_inactivo_da_404(client, products, db):
    p = db.query(Product).filter_by(slug="9pm").one()
    p.active = False
    db.commit()
    assert client.get("/products/9pm").status_code == 404


def test_producto_nuevo_creado_directo_en_db(client, db):
    db.add(
        Product(
            slug="prueba",
            name="Prueba",
            brand="Marca",
            category="daily",
            tone="noir",
            price=Decimal("50.00"),
            image="/perfumes/prueba-1.webp",
            gallery=[],
            stock=3,
        )
    )
    db.commit()
    res = client.get("/products/prueba")
    assert res.status_code == 200
    assert res.json()["oldPrice"] is None
