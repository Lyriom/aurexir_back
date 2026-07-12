from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Product
from app.schemas.product import ProductOut

router = APIRouter(prefix="/products", tags=["catálogo"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[ProductOut])
def list_products(db: DbDep) -> list[ProductOut]:
    products = db.scalars(
        select(Product).where(Product.active.is_(True)).order_by(Product.created_at, Product.slug)
    ).all()
    return [ProductOut.from_model(p) for p in products]


@router.get("/{slug}", response_model=ProductOut)
def get_product(slug: str, db: DbDep) -> ProductOut:
    product = db.scalar(select(Product).where(Product.slug == slug, Product.active.is_(True)))
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return ProductOut.from_model(product)
