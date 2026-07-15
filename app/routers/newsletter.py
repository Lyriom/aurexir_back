from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NewsletterSubscriber
from app.rate_limit import limiter
from app.schemas.newsletter import NewsletterIn
from app.services import discounts
from app.services import email as email_service

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def subscribe(
    request: Request, payload: NewsletterIn, response: Response, db: DbDep
) -> dict[str, str | bool]:
    """Alta idempotente + código de descuento de bienvenida por email.

    El código es único por email (repetir la suscripción no genera otro); si
    sigue sin usarse se reenvía el mismo. El envío es best-effort: si Resend
    falla la suscripción queda registrada igualmente.
    """
    email = payload.email.strip().lower()
    already = (
        db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email))
        is not None
    )
    if not already:
        db.add(NewsletterSubscriber(email=email, locale=payload.locale))
    code = discounts.get_or_create_for_email(db, email)
    db.commit()

    sent = False
    if code.used_at is None:
        sent = email_service.send_discount_email(email, code.code, code.percent, payload.locale)

    if already:
        response.status_code = status.HTTP_200_OK
        return {"status": "already_subscribed", "discount_email_sent": sent}
    return {"status": "subscribed", "discount_email_sent": sent}
