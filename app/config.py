"""Configuración de la aplicación vía variables de entorno (.env)."""

from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://aurexir:aurexir@localhost:5432/aurexir"

    jwt_secret: str = "dev-secret-cambia-esto"
    jwt_expires_min: int = 10080  # 7 días

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

    # Envíos (solo EE. UU.)
    free_shipping_threshold: Decimal = Decimal("200")
    shipping_standard: Decimal = Decimal("6.95")
    shipping_express: Decimal = Decimal("14.95")

    # Umbral para el aviso de bajo stock en métricas de admin
    low_stock_threshold: int = 5

    # Desactivable en tests
    rate_limit_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
