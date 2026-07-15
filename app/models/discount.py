from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import new_uuid, utcnow


class DiscountCode(Base):
    """Código de descuento del newsletter: uno por email, de un solo uso.

    Se consume SOLO cuando el webhook confirma el pago (misma filosofía que el
    stock): un pedido pending/cancelado no gasta el código.
    """

    __tablename__ = "discount_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    percent: Mapped[int] = mapped_column(Integer, default=15)
    # Sin FK: el pedido que lo consumió se registra a posteriori desde el webhook.
    order_id: Mapped[str | None] = mapped_column(String(36))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
