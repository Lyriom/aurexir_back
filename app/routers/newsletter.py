from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NewsletterSubscriber
from app.schemas.newsletter import NewsletterIn

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def subscribe(payload: NewsletterIn, response: Response, db: DbDep) -> dict[str, str]:
    """Alta idempotente: si el email ya está suscrito responde 200 en vez de 201."""
    email = payload.email.strip().lower()
    if db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)):
        response.status_code = status.HTTP_200_OK
        return {"status": "already_subscribed"}
    db.add(NewsletterSubscriber(email=email, locale=payload.locale))
    db.commit()
    return {"status": "subscribed"}
