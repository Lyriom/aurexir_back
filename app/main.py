"""Punto de entrada: create_app con CORS, rate-limit, routers y /health."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.rate_limit import limiter
from app.routers import (
    admin,
    auth,
    checkout,
    discounts,
    newsletter,
    orders,
    products,
    shipping,
    webhooks,
)


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 con la forma {detail} que asume el front (no el {error} de slowapi)."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiados intentos. Inténtalo de nuevo en un minuto."},
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AUREXIR API", version="0.1.0")

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    allowed_origins = {settings.frontend_origin, "https://aurexir.com", "https://www.aurexir.com"}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(shipping.router)
    app.include_router(checkout.router)
    app.include_router(orders.router)
    app.include_router(newsletter.router)
    app.include_router(discounts.router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
