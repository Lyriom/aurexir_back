"""Schemas de producto. La forma pública replica src/data/products.js del front:
`id` es el slug y los campos van en camelCase (oldPrice, isNew, isBest)."""

from typing import Literal

from pydantic import BaseModel

from app.models import Product

Category = Literal["multi", "daily", "night", "special"]


class ProductOut(BaseModel):
    id: str  # slug — identificador público que usa el front
    name: str
    brand: str
    category: str
    tag: str | None = None
    tone: str
    price: float
    oldPrice: float | None = None
    image: str
    gallery: list[str]
    desc: dict
    notes: dict
    rating: float
    reviews: int
    isNew: bool
    isBest: bool
    stock: int

    @classmethod
    def from_model(cls, p: Product) -> "ProductOut":
        return cls(
            id=p.slug,
            name=p.name,
            brand=p.brand,
            category=p.category,
            tag=p.tag,
            tone=p.tone,
            price=float(p.price),
            oldPrice=float(p.old_price) if p.old_price is not None else None,
            image=p.image,
            gallery=p.gallery or [],
            desc={"en": p.desc_en, "es": p.desc_es},
            notes=p.notes or {},
            rating=p.rating,
            reviews=p.reviews,
            isNew=p.is_new,
            isBest=p.is_best,
            stock=p.stock,
        )
