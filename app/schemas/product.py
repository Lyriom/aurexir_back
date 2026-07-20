"""Schemas de producto. La forma pública replica src/data/products.js del front:
`id` es el slug y los campos van en camelCase (oldPrice, isNew, isBest)."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

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
    active: bool

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
            active=p.active,
        )


# ---- Admin ----


class ProductAdminOut(ProductOut):
    """Como la vista pública (ya incluye `active`), más el uuid interno."""

    uuid: str  # id real en base de datos (el PATCH acepta uuid o slug)

    @classmethod
    def from_model(cls, p: Product) -> "ProductAdminOut":
        base = ProductOut.from_model(p)
        return cls(**base.model_dump(), uuid=p.id)


class LocalizedText(BaseModel):
    en: str = ""
    es: str = ""


class ProductCreateIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=120)
    name: str = Field(min_length=1, max_length=200)
    brand: str = Field(min_length=1, max_length=120)
    category: Category
    tag: str | None = Field(default=None, max_length=40)
    tone: str = Field(default="noir", max_length=20)
    price: Decimal = Field(gt=0, decimal_places=2)
    oldPrice: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    image: str = Field(default="", max_length=300)
    gallery: list[str] = Field(default_factory=list)
    desc: LocalizedText = Field(default_factory=LocalizedText)
    notes: dict = Field(default_factory=dict)
    rating: float = Field(default=0.0, ge=0, le=5)
    reviews: int = Field(default=0, ge=0)
    isNew: bool = False
    isBest: bool = False
    stock: int = Field(default=0, ge=0)
    active: bool = True


class ProductUpdateIn(BaseModel):
    """Actualización parcial. El stock tiene su propio endpoint (auditoría)."""

    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, min_length=1, max_length=120)
    category: Category | None = None
    tag: str | None = Field(default=None, max_length=40)
    tone: str | None = Field(default=None, max_length=20)
    price: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    oldPrice: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    image: str | None = Field(default=None, max_length=300)
    gallery: list[str] | None = None
    desc: LocalizedText | None = None
    notes: dict | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    reviews: int | None = Field(default=None, ge=0)
    isNew: bool | None = None
    isBest: bool | None = None
    active: bool | None = None


class StockUpdateIn(BaseModel):
    """Ajuste de stock por delta (el front manda +N para reponer, -N para reducir)."""

    delta: int = Field(description="Cambio de stock: positivo repone, negativo reduce")
    reason: Literal["restock", "manual"] = "manual"
