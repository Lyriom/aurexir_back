from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Order, OrderItem
from app.schemas.order import OrderOut
from app.security import CurrentUser

router = APIRouter(prefix="/orders", tags=["pedidos"])

DbDep = Annotated[Session, Depends(get_db)]


@router.get("/mine", response_model=list[OrderOut])
def my_orders(user: CurrentUser, db: DbDep) -> list[OrderOut]:
    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.items).selectinload(OrderItem.product))
        .order_by(Order.created_at.desc())
    ).all()
    return [OrderOut.from_model(o) for o in orders]
