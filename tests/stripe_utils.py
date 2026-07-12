"""Utilidades para simular Stripe en tests: firma de webhooks y sesión falsa."""

import hashlib
import hmac
import json
import time
from types import SimpleNamespace

WEBHOOK_SECRET = "whsec_test_dummy"  # debe coincidir con conftest


def fake_session(session_id: str = "cs_test_123") -> SimpleNamespace:
    return SimpleNamespace(id=session_id, url=f"https://checkout.stripe.com/c/pay/{session_id}")


def sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Cabecera Stripe-Signature válida para el payload (esquema t=..,v1=..)."""
    timestamp = int(time.time())
    signed = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def checkout_completed_event(
    session_id: str = "cs_test_123",
    payment_intent: str = "pi_test_123",
    amount_tax: int = 0,
    amount_total: int | None = None,
) -> bytes:
    event = {
        "id": "evt_test_1",
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_intent": payment_intent,
                "amount_total": amount_total,
                "total_details": {"amount_tax": amount_tax},
                "shipping_details": {
                    "name": "Cliente Test",
                    "address": {
                        "line1": "350 5th Ave",
                        "city": "New York",
                        "state": "NY",
                        "postal_code": "10118",
                        "country": "US",
                    },
                },
            }
        },
    }
    return json.dumps(event).encode()


def checkout_expired_event(session_id: str = "cs_test_123") -> bytes:
    event = {
        "id": "evt_test_2",
        "object": "event",
        "type": "checkout.session.expired",
        "data": {"object": {"id": session_id, "object": "checkout.session"}},
    }
    return json.dumps(event).encode()
