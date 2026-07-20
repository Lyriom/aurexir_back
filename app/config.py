"""Configuración de la aplicación vía variables de entorno (.env)."""

from decimal import Decimal
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secretos placeholder que NUNCA deben llegar a producción: si el JWT_SECRET es
# uno de estos (o demasiado corto), la app se niega a arrancar. Un secreto débil
# hace que cualquiera pueda forjar tokens de admin.
_INSECURE_JWT_SECRETS = {
    "dev-secret-cambia-esto",
    "dev-secret-local-cambia-esto-antes-de-produccion",
    "cambia-esto",
    "cambia-esto-por-un-secreto-aleatorio-largo",
    "change-me",
    "changeme",
    "secret",
}
_MIN_JWT_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://aurexir:aurexir@localhost:5432/aurexir"

    jwt_secret: str = "dev-secret-cambia-esto"
    jwt_expires_min: int = 10080  # 7 días

    # Tope de tamaño de cuerpo de petición (anti-DoS por payload gigante).
    max_body_bytes: int = 1_000_000  # 1 MB

    admin_email: str = "admin@aurexir.com"
    admin_password: str = "cambia-esto"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Resend (envío de correos). Con la key vacía el envío se omite (no-op).
    resend_api_key: str = ""
    # Hasta verificar el dominio en Resend solo puede ser onboarding@resend.dev.
    email_from: str = "AUREXIR <onboarding@resend.dev>"
    newsletter_discount_percent: int = 15

    frontend_origin: str = "http://localhost:5173"

    # Envíos (solo EE. UU.): tarifa plana, sin cálculo por ZIP.
    free_shipping_threshold: Decimal = Decimal("200")
    shipping_standard: Decimal = Decimal("20")
    shipping_eco: Decimal = Decimal("30")  # envío ecológico (carbono neutro)

    # Umbral para el aviso de bajo stock en métricas de admin
    low_stock_threshold: int = 5

    # Desactivable en tests
    rate_limit_enabled: bool = True

    @model_validator(mode="after")
    def _reject_insecure_jwt_secret(self) -> "Settings":
        secret = self.jwt_secret.strip()
        if secret in _INSECURE_JWT_SECRETS or len(secret) < _MIN_JWT_SECRET_LEN:
            raise ValueError(
                "JWT_SECRET inseguro o ausente. Define un valor aleatorio de "
                f"{_MIN_JWT_SECRET_LEN}+ caracteres, p. ej. `openssl rand -hex 32`."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
