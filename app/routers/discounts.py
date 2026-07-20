from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.rate_limit import limiter
from app.schemas.discount import DiscountValidateIn, DiscountValidateOut
from app.services import discounts

router = APIRouter(prefix="/discounts", tags=["descuentos"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/validate", response_model=DiscountValidateOut)
@limiter.limit("20/minute")
def validate_code(request: Request, payload: DiscountValidateIn, db: DbDep) -> DiscountValidateOut:
    """Para que el front compruebe un código antes del checkout (siempre 200).

    Rate-limited para que no se puedan sondear códigos por fuerza bruta.
    """
    discount = discounts.find_valid(db, payload.code)
    if discount is None:
        return DiscountValidateOut(valid=False, code=payload.code.strip().upper(), percent=0)
    return DiscountValidateOut(valid=True, code=discount.code, percent=discount.percent)
