from pydantic import BaseModel, Field


class DiscountValidateIn(BaseModel):
    code: str = Field(min_length=4, max_length=40)


class DiscountValidateOut(BaseModel):
    valid: bool
    code: str | None = None
    percent: int | None = None
