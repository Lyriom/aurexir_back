from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import new_uuid, utcnow


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("stock >= 0", name="ck_products_stock_no_negativo"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    # El front usa el slug como identificador público del producto.
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))  # multi | daily | night | special
    tag: Mapped[str | None] = mapped_column(String(40))  # p. ej. 'niche'
    tone: Mapped[str] = mapped_column(String(20), default="noir")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    old_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    image: Mapped[str] = mapped_column(String(300))
    gallery: Mapped[list] = mapped_column(JSON, default=list)  # 3 urls
    desc_en: Mapped[str] = mapped_column(Text, default="")
    desc_es: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[dict] = mapped_column(JSON, default=dict)  # {top|heart|base: {en, es}}
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    reviews: Mapped[int] = mapped_column(Integer, default=0)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="product")


class InventoryMovement(Base):
    """Auditoría del inventario: todo cambio de stock deja un registro."""

    __tablename__ = "inventory_movements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer)  # +/- unidades aplicadas
    reason: Mapped[str] = mapped_column(String(20))  # sale | restock | manual | cancel
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    product: Mapped[Product] = relationship(back_populates="movements")
