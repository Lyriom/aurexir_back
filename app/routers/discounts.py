from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.discount import DiscountValidateIn, DiscountValidateOut
from app.services import discounts

router = APIRouter(prefix="/discounts", tags=["descuentos"])

DbDep = Annotated[Session, Depends(get_db)]


@router.post("/validate", response_model=DiscountValidateOut)
def validate_code(payload: DiscountValidateIn, db: DbDep) -> DiscountValidateOut:
    """Para que el front compruebe un código antes del checkout (siempre 200)."""
    discount = discounts.find_valid(db, payload.code)
    if discount is None:
        return DiscountValidateOut(valid=False)
    return DiscountValidateOut(valid=True, code=discount.code, percent=discount.percent)
