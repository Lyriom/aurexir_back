"""Endpoints de administración. Todos exigen Bearer + role=admin (403 si no)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import ORDER_STATUSES, PAID_STATUSES, VALID_TRANSITIONS, Order, OrderItem
from app.schemas.order import OrderAdminOut, OrderStatusIn
from app.security import AdminUser
from app.services.inventory import deduct_for_order, restock_for_order

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
