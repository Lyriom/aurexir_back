"""Endpoints de administración. Todos exigen Bearer + role=admin (403 si no)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import (
    ORDER_STATUSES,
    PAID_STATUSES,
    VALID_TRANSITIONS,
    Order,
    OrderItem,
    Product,
)
from app.schemas.order import OrderAdminOut, OrderStatusIn
from app.schemas.product import ProductAdminOut, ProductCreateIn, ProductUpdateIn, StockUpdateIn
from app.security import AdminUser
from app.services.inventory import apply_movement, deduct_for_order, restock_for_order
from app.services.metrics import compute_metrics

router = APIRouter(prefix="/admin", tags=["admin"])

DbDep = Annotated[Session, Depends(get_db)]


# ---- Pedidos ----


@router.get("/orders", response_model=list[OrderAdminOut])
def list_orders(
    admin: AdminUser,
    db: DbDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[OrderAdminOut]:
    query = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.user),
        )
        .order_by(Order.created_at.desc())
    )
    if status_filter:
        if status_filter not in ORDER_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Estado desconocido: {status_filter}",
            )
        query = query.where(Order.status == status_filter)
    return [OrderAdminOut.from_model(o) for o in db.scalars(query).all()]


@router.patch("/orders/{order_id}", response_model=OrderAdminOut)
def update_order_status(
    order_id: str, payload: OrderStatusIn, admin: AdminUser, db: DbDep
) -> OrderAdminOut:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")

    new_status = payload.status
    if new_status not in VALID_TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transición inválida: {order.status} → {new_status}",
        )

    was_paid = order.status in PAID_STATUSES
    order.status = new_status

    if new_status == "canceled" and was_paid:
        # La orden pagada ya descontó stock: se repone (movimiento `cancel`).
        restock_for_order(db, order)
    elif new_status == "paid":
        # Pago confirmado manualmente por el admin (fuera del webhook).
        deduct_for_order(db, order)

    db.commit()
    return OrderAdminOut.from_model(order)


# ---- Métricas ----


@router.get("/metrics")
def metrics(
    admin: AdminUser,
    db: DbDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict:
    return compute_metrics(db, days)


# ---- Productos ----


def _get_product(db: Session, product_id: str) -> Product:
    """Busca por uuid interno o por slug (el front usa el slug como id)."""
    product = db.get(Product, product_id) or db.scalar(
        select(Product).where(Product.slug == product_id)
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
    return product


@router.get("/products", response_model=list[ProductAdminOut])
def list_all_products(admin: AdminUser, db: DbDep) -> list[ProductAdminOut]:
    products = db.scalars(select(Product).order_by(Product.created_at, Product.slug)).all()
    return [ProductAdminOut.from_model(p) for p in products]


@router.post("/products", response_model=ProductAdminOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreateIn, admin: AdminUser, db: DbDep) -> ProductAdminOut:
    if db.scalar(select(Product).where(Product.slug == payload.slug)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un producto con slug '{payload.slug}'",
        )
    product = Product(
        slug=payload.slug,
        name=payload.name,
        brand=payload.brand,
        category=payload.category,
        tag=payload.tag,
        tone=payload.tone,
        price=payload.price,
        old_price=payload.oldPrice,
        image=payload.image,
        gallery=payload.gallery,
        desc_en=payload.desc.en,
        desc_es=payload.desc.es,
        notes=payload.notes,
        rating=payload.rating,
        reviews=payload.reviews,
        is_new=payload.isNew,
        is_best=payload.isBest,
        stock=0,  # el stock inicial entra como movimiento, para que quede auditado
        active=payload.active,
    )
    db.add(product)
    db.flush()
    if payload.stock:
        apply_movement(db, product, payload.stock, "restock")
    db.commit()
    return ProductAdminOut.from_model(product)


@router.patch("/products/{product_id}", response_model=ProductAdminOut)
def update_product(
    product_id: str, payload: ProductUpdateIn, admin: AdminUser, db: DbDep
) -> ProductAdminOut:
    product = _get_product(db, product_id)
    changes = payload.model_dump(exclude_unset=True)

    new_slug = changes.get("slug")
    if (
        new_slug
        and new_slug != product.slug
        and db.scalar(select(Product).where(Product.slug == new_slug))
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un producto con slug '{new_slug}'",
        )

    renames = {"oldPrice": "old_price", "isNew": "is_new", "isBest": "is_best"}
    for field, value in changes.items():
        if field == "desc":
            if value is not None:
                product.desc_en = value["en"]
                product.desc_es = value["es"]
            continue
        setattr(product, renames.get(field, field), value)

    db.commit()
    return ProductAdminOut.from_model(product)


@router.patch("/products/{product_id}/stock", response_model=ProductAdminOut)
def update_stock(
    product_id: str, payload: StockUpdateIn, admin: AdminUser, db: DbDep
) -> ProductAdminOut:
    product = _get_product(db, product_id)
    delta = payload.stock - product.stock
    apply_movement(db, product, delta, payload.reason)
    db.commit()
    return ProductAdminOut.from_model(product)
