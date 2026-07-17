"""Envío de correos vía Resend.

Best-effort: si RESEND_API_KEY está vacío o Resend falla, se registra y se
devuelve False sin romper el request (ninguna operación de negocio debe fallar
por el proveedor de email).
"""

import logging

import resend

from app.config import get_settings
from app.models import Order

logger = logging.getLogger(__name__)

GOLD = "#c9a25f"
CREAM = "#f4f1ea"
MUTED = "#b9b4a8"
FAINT = "#6f6a5e"


def _send(to_email: str, subject: str, html: str) -> bool:
    settings = get_settings()
    if not settings.resend_api_key:
        logger.info("RESEND_API_KEY vacío; no se envía '%s' a %s", subject, to_email)
        return False
    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send(
            {"from": settings.email_from, "to": [to_email], "subject": subject, "html": html}
        )
    except Exception:
        logger.exception("Fallo enviando '%s' a %s", subject, to_email)
        return False
    return True


def _layout(inner: str) -> str:
    """Envuelve el contenido en la tarjeta oscura con el logotipo de la marca."""
    return f"""\
<div style="margin:0;padding:0;background-color:#0c0c0e;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#0c0c0e;padding:40px 16px;">
    <tr><td align="center">
      <table role="presentation" width="520" cellpadding="0" cellspacing="0"
             style="max-width:520px;width:100%;background-color:#121216;border:1px solid #2a2a30;
                    border-radius:12px;padding:40px 32px;
                    font-family:Georgia,'Times New Roman',serif;">
        <tr><td align="center" style="padding-bottom:28px;">
          <span style="font-size:22px;letter-spacing:6px;color:{GOLD};">AUREXIR</span>
        </td></tr>
        {inner}
      </table>
    </td></tr>
  </table>
</div>
"""


# ---- Código de descuento del newsletter ----

_DISCOUNT = {
    "es": {
        "subject": "Tu código de {percent}% de descuento — AUREXIR",
        "headline": "Bienvenido a AUREXIR",
        "body": (
            "Gracias por suscribirte. Usa este código en tu primera compra "
            "y llévate un <strong>{percent}% de descuento</strong>:"
        ),
        "footer": "Válido para un solo uso en aurexir.com",
    },
    "en": {
        "subject": "Your {percent}% off code — AUREXIR",
        "headline": "Welcome to AUREXIR",
        "body": (
            "Thanks for subscribing. Use this code on your first purchase "
            "to get <strong>{percent}% off</strong>:"
        ),
        "footer": "Valid for a single use at aurexir.com",
    },
}


def send_discount_email(to_email: str, code: str, percent: int, locale: str = "en") -> bool:
    t = _DISCOUNT.get(locale, _DISCOUNT["en"])
    inner = f"""\
        <tr><td align="center" style="padding-bottom:12px;">
          <span style="font-size:18px;color:{CREAM};">{t["headline"]}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:24px;">
          <span style="font-size:14px;line-height:1.6;color:{MUTED};">\
{t["body"].format(percent=percent)}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:24px;">
          <span style="display:inline-block;padding:14px 28px;border:1px dashed {GOLD};
                       border-radius:8px;font-size:22px;letter-spacing:3px;color:{GOLD};
                       font-family:'Courier New',monospace;">{code}</span>
        </td></tr>
        <tr><td align="center">
          <span style="font-size:12px;color:{FAINT};">{t["footer"]}</span>
        </td></tr>
"""
    subject = t["subject"].format(percent=percent)
    return _send(to_email, subject, _layout(inner))


# ---- Correos de pedido (confirmación + tracking) ----


def _money(amount) -> str:
    return f"${float(amount):.2f}"


def _items_rows(order: Order) -> str:
    rows = ""
    for item in order.items:
        rows += f"""\
          <tr>
            <td style="padding:8px 0;font-size:14px;color:{CREAM};">\
{item.brand_snapshot} — {item.name_snapshot} × {item.qty}</td>
            <td align="right" style="padding:8px 0;font-size:14px;color:{CREAM};">\
{_money(item.unit_price * item.qty)}</td>
          </tr>"""
    return rows


def _summary_table(order: Order, labels: dict) -> str:
    discount = ""
    if float(order.discount_amount) > 0:
        discount = f"""\
          <tr>
            <td style="padding:4px 0;font-size:13px;color:{MUTED};">\
{labels["discount"]} ({order.discount_code})</td>
            <td align="right" style="padding:4px 0;font-size:13px;color:{MUTED};">\
-{_money(order.discount_amount)}</td>
          </tr>"""
    return f"""\
        <tr><td colspan="2" style="padding-top:20px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="border-top:1px solid #2a2a30;padding-top:12px;">
{_items_rows(order)}
            <tr><td colspan="2" style="border-top:1px solid #2a2a30;padding-top:10px;"></td></tr>
          <tr>
            <td style="padding:4px 0;font-size:13px;color:{MUTED};">{labels["subtotal"]}</td>
            <td align="right" style="padding:4px 0;font-size:13px;color:{MUTED};">\
{_money(order.subtotal)}</td>
          </tr>
{discount}
          <tr>
            <td style="padding:4px 0;font-size:13px;color:{MUTED};">{labels["shipping"]}</td>
            <td align="right" style="padding:4px 0;font-size:13px;color:{MUTED};">\
{_money(order.shipping_cost)}</td>
          </tr>
          <tr>
            <td style="padding:8px 0 0;font-size:16px;color:{CREAM};">{labels["total"]}</td>
            <td align="right" style="padding:8px 0 0;font-size:16px;color:{GOLD};">\
{_money(order.total)}</td>
          </tr>
          </table>
        </td></tr>
"""


_CONFIRMATION = {
    "es": {
        "subject": "Confirmación de tu pedido {number} — AUREXIR",
        "headline": "¡Gracias por tu compra!",
        "intro": (
            "Hemos recibido tu pedido <strong>{number}</strong> y ya lo estamos "
            "preparando. Lo recibirás en un plazo de <strong>3 a 5 días "
            "laborables</strong>. Te avisaremos por correo cuando salga con su "
            "número de seguimiento."
        ),
        "labels": {
            "subtotal": "Subtotal",
            "discount": "Descuento",
            "shipping": "Envío",
            "total": "Total",
        },
        "footer": "Cualquier duda, responde a este correo. AUREXIR · aurexir.com",
    },
    "en": {
        "subject": "Your order {number} is confirmed — AUREXIR",
        "headline": "Thank you for your order!",
        "intro": (
            "We've received your order <strong>{number}</strong> and we're "
            "preparing it now. You'll receive it within <strong>3 to 5 business "
            "days</strong>. We'll email you the tracking number as soon as it ships."
        ),
        "labels": {
            "subtotal": "Subtotal",
            "discount": "Discount",
            "shipping": "Shipping",
            "total": "Total",
        },
        "footer": "Questions? Just reply to this email. AUREXIR · aurexir.com",
    },
}


def send_order_confirmation(to_email: str, order: Order) -> bool:
    try:
        return _build_and_send_confirmation(to_email, order)
    except Exception:
        logger.exception("Fallo construyendo la confirmación del pedido %s", order.number)
        return False


def _build_and_send_confirmation(to_email: str, order: Order) -> bool:
    t = _CONFIRMATION.get(order.locale, _CONFIRMATION["en"])
    inner = f"""\
        <tr><td align="center" style="padding-bottom:12px;">
          <span style="font-size:18px;color:{CREAM};">{t["headline"]}</span>
        </td></tr>
        <tr><td style="padding-bottom:8px;">
          <span style="font-size:14px;line-height:1.6;color:{MUTED};">\
{t["intro"].format(number=order.number)}</span>
        </td></tr>
{_summary_table(order, t["labels"])}
        <tr><td align="center" style="padding-top:28px;">
          <span style="font-size:12px;color:{FAINT};">{t["footer"]}</span>
        </td></tr>
"""
    subject = t["subject"].format(number=order.number)
    return _send(to_email, subject, _layout(inner))


_TRACKING = {
    "es": {
        "subject": "Tu pedido {number} va en camino — AUREXIR",
        "headline": "¡Tu pedido está en camino!",
        "intro": (
            "Buenas noticias: tu pedido <strong>{number}</strong> ya ha salido. "
            "Aquí tienes tu número de seguimiento:"
        ),
        "carrier": "Transportista",
        "button": "Seguir mi envío",
        "footer": "Gracias por confiar en AUREXIR · aurexir.com",
    },
    "en": {
        "subject": "Your order {number} is on its way — AUREXIR",
        "headline": "Your order is on its way!",
        "intro": (
            "Good news: your order <strong>{number}</strong> has shipped. "
            "Here is your tracking number:"
        ),
        "carrier": "Carrier",
        "button": "Track my shipment",
        "footer": "Thank you for choosing AUREXIR · aurexir.com",
    },
}


def send_tracking_email(to_email: str, order: Order) -> bool:
    try:
        return _build_and_send_tracking(to_email, order)
    except Exception:
        logger.exception("Fallo construyendo el correo de tracking del pedido %s", order.number)
        return False


def _build_and_send_tracking(to_email: str, order: Order) -> bool:
    t = _TRACKING.get(order.locale, _TRACKING["en"])
    carrier = ""
    if order.tracking_carrier:
        carrier = f"""\
        <tr><td align="center" style="padding-bottom:16px;">
          <span style="font-size:13px;color:{MUTED};">\
{t["carrier"]}: {order.tracking_carrier}</span>
        </td></tr>"""
    button = ""
    if order.tracking_url:
        button = f"""\
        <tr><td align="center" style="padding-top:8px;">
          <a href="{order.tracking_url}" style="display:inline-block;padding:14px 32px;
             background-color:{GOLD};color:#0c0c0e;text-decoration:none;border-radius:8px;
             font-size:14px;letter-spacing:1px;">{t["button"]}</a>
        </td></tr>"""
    inner = f"""\
        <tr><td align="center" style="padding-bottom:12px;">
          <span style="font-size:18px;color:{CREAM};">{t["headline"]}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:20px;">
          <span style="font-size:14px;line-height:1.6;color:{MUTED};">\
{t["intro"].format(number=order.number)}</span>
        </td></tr>
        <tr><td align="center" style="padding-bottom:16px;">
          <span style="display:inline-block;padding:14px 28px;border:1px dashed {GOLD};
                       border-radius:8px;font-size:20px;letter-spacing:2px;color:{GOLD};
                       font-family:'Courier New',monospace;">{order.tracking_number}</span>
        </td></tr>
{carrier}
{button}
        <tr><td align="center" style="padding-top:28px;">
          <span style="font-size:12px;color:{FAINT};">{t["footer"]}</span>
        </td></tr>
"""
    subject = t["subject"].format(number=order.number)
    return _send(to_email, subject, _layout(inner))
