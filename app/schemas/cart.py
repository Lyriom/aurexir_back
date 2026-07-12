from pydantic import BaseModel, Field


class CartItemIn(BaseModel):
    """Línea de carrito tal como la envía el front: id = slug del producto."""

    id: str = Field(min_length=1, max_length=120)
    qty: int = Field(ge=1, le=99)
