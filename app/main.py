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


# Cabeceras que se añaden a TODAS las respuestas. Es una API JSON (no sirve HTML),
# así que la CSP más restrictiva es segura y bloquea cualquier intento de embeber.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store",
}


def _add_security_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_layer(request: Request, call_next):
        # Rechaza cuerpos gigantes antes de bufferizarlos (anti-DoS de memoria).
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > get_settings().max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Cuerpo de la petición demasiado grande"},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "Content-Length inválido"}
                )
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AUREXIR API", version="0.1.0")

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    _add_security_middleware(app)

    allowed_origins = {settings.frontend_origin, "https://aurexir.com", "https://www.aurexir.com"}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
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
