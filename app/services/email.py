"""Envío de correos vía Resend.

Best-effort: si RESEND_API_KEY está vacío o Resend falla, se registra y se
devuelve False sin romper el request (una suscripción nunca debe fallar por
el proveedor de email).
"""

import logging

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)

_SUBJECTS = {
    "es": "Tu código de {percent}% de descuento — AUREXIR",
    "en": "Your {percent}% off code — AUREXIR",
}

_HEADLINES = {
    "es": "Bienvenido a AUREXIR",
    "en": "Welcome to AUREXIR",
}

_BODIES = {
    "es": (
        "Gracias por suscribirte. Usa este código en tu primera compra "
        "y llévate un <strong>{percent}% de descuento</strong>:"
    ),
    "en": (
        "Thanks for subscribing. Use this code on your first purchase "
        "to get <strong>{percent}% off</strong>:"
    ),
}

_FOOTERS = {
    "es": "Válido para un solo uso en aurexir.com",
    "en": "Valid for a single use at aurexir.com",
}


def _discount_html(code: str, percent: int, locale: str) -> str:
    headline = _HEADLINES.get(locale, _HEADLINES["en"])
    body = _BODIES.get(locale, _BODIES["en"]).format(percent=percent)
    footer = _FOOTERS.get(locale, _FOOTERS["en"])
    return f"""\
<div style="margin:0;padding:0;background-color:#0c0c0e;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#0c0c0e;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="480" cellpadding="0" cellspacing="0"
             style="max-width:480px;width:100%;background-color:#121216;border:1px solid #2a2a30;
                    border-radius:12px;padding:40px 32px;
                    font-family:Georgia,'Times New Roman',serif;">
        <tr><td align="center" style="padding-bottom:24px;">
          <span style="font-size:22px;letter-spacing:6px;color:#c9a25f;">AUREXIR</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:12px;">
          <span style="font-size:18px;color:#f4f1ea;">{headline}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:24px;">
          <span style="font-size:14px;line-height:1.6;color:#b9b4a8;">{body}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:24px;">
          <span style="display:inline-block;padding:14px 28px;border:1px dashed #c9a25f;
                       border-radius:8px;font-size:22px;letter-spacing:3px;color:#c9a25f;
                       font-family:'Courier New',monospace;">{code}</span>
        </td></tr>
        <tr><td align="center">
          <span style="font-size:12px;color:#6f6a5e;">{footer}</span>
        </td></tr>
      </table>
    </td></tr>
  </table>
</div>
"""


def send_discount_email(to_email: str, code: str, percent: int, locale: str = "en") -> bool:
    settings = get_settings()
    if not settings.resend_api_key:
        logger.info("RESEND_API_KEY vacío; no se envía el código de descuento a %s", to_email)
        return False

    subject = _SUBJECTS.get(locale, _SUBJECTS["en"]).format(percent=percent)
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to_email],
                "subject": subject,
                "html": _discount_html(code, percent, locale),
            }
        )
    except Exception:
        logger.exception("Fallo enviando el código de descuento a %s", to_email)
        return False
    return True
