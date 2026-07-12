"""Seed idempotente: usuario admin + catálogo de 20 productos.

El catálogo vive en app/data/products_seed.json, generado desde
../aurexir/src/data/products.js (la fuente de verdad del front — el slug que
usa el front como `id` aquí es Product.slug). Ejecutar con `python -m app.seed`.
"""

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Product, User
from app.security import hash_password

SEED_FILE = Path(__file__).parent / "data" / "products_seed.json"
INITIAL_STOCK = 10


def seed_admin(db: Session) -> bool:
    """Crea el admin desde ADMIN_EMAIL/ADMIN_PASSWORD si no existe."""
    settings = get_settings()
    email = settings.admin_email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        return False
    db.add(
        User(
            email=email,
            name="AUREXIR Admin",
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    return True


def seed_products(db: Session) -> int:
    """Inserta los productos del catálogo que aún no existan (por slug)."""
    raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    existing = set(db.scalars(select(Product.slug)))
    created = 0
    for item in raw:
        if item["id"] in existing:
            continue
        db.add(
            Product(
                slug=item["id"],
                name=item["name"],
                brand=item["brand"],
                category=item["category"],
                tag=item.get("tag"),
                tone=item.get("tone", "noir"),
                price=Decimal(str(item["price"])),
                old_price=Decimal(str(item["oldPrice"])) if item.get("oldPrice") else None,
                image=item["image"],
                gallery=item.get("gallery", []),
                desc_en=item.get("desc", {}).get("en", ""),
                desc_es=item.get("desc", {}).get("es", ""),
                notes=item.get("notes", {}),
                rating=item.get("rating", 0.0),
                reviews=item.get("reviews", 0),
                is_new=bool(item.get("isNew")),
                is_best=bool(item.get("isBest")),
                stock=INITIAL_STOCK,
                active=True,
            )
        )
        created += 1
    return created


def run(db: Session) -> None:
    admin_created = seed_admin(db)
    products_created = seed_products(db)
    db.commit()
    print(
        f"Seed: admin {'creado' if admin_created else 'ya existía'}, "
        f"{products_created} productos nuevos."
    )


def main() -> None:
    from app.database import SessionLocal

    with SessionLocal() as db:
        run(db)


if __name__ == "__main__":
    main()
