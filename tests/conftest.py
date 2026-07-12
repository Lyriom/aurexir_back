"""Arnés de tests: SQLite in-memory + TestClient con get_db sobreescrito.

Las variables de entorno se fijan ANTES de importar la app para que
Settings (lru_cache) las lea. El rate-limit se desactiva en tests.
"""

import os

os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-suficientemente-largo-para-hs256"
os.environ["ADMIN_EMAIL"] = "admin@aurexir.com"
os.environ["ADMIN_PASSWORD"] = "admin-password-test"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_dummy"
os.environ["FREE_SHIPPING_THRESHOLD"] = "200"
os.environ["SHIPPING_STANDARD"] = "6.95"
os.environ["SHIPPING_EXPRESS"] = "14.95"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import seed  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def products(db):
    """Carga el catálogo real del seed (20 productos, stock 10)."""
    seed.seed_products(db)
    db.commit()
    return db


@pytest.fixture()
def customer_token(client):
    res = client.post(
        "/auth/register",
        json={"email": "cliente@test.com", "password": "password123", "name": "Cliente"},
    )
    assert res.status_code == 201
    return res.json()["access_token"]


@pytest.fixture()
def customer_headers(customer_token):
    return {"Authorization": f"Bearer {customer_token}"}


@pytest.fixture()
def admin_headers(db):
    admin = User(
        email="admin@aurexir.com",
        name="Admin",
        password_hash=hash_password("admin-password-test"),
        role="admin",
    )
    db.add(admin)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(admin)}"}
