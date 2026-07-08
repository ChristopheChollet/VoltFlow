"""Stripe webhook signature verification — pure crypto check, no network calls."""

import hashlib
import hmac
import json
import time

import pytest
import stripe

from app.services import stripe_service

WEBHOOK_SECRET = "whsec_test_secret"


def _sign_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    timestamp = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _event_payload(event_type: str) -> bytes:
    return json.dumps(
        {
            "id": "evt_1",
            "object": "event",
            "type": event_type,
            "data": {"object": {"id": "cs_test_1"}},
        }
    ).encode()


def test_verify_webhook_signature_valid(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = _event_payload("checkout.session.completed")
    signature = _sign_payload(payload, WEBHOOK_SECRET)

    event = stripe_service.verify_webhook_signature(payload, signature)

    assert event["type"] == "checkout.session.completed"
    assert event["data"]["object"]["id"] == "cs_test_1"


def test_verify_webhook_signature_wrong_secret(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = _event_payload("checkout.session.completed")
    bad_signature = _sign_payload(payload, "wrong-secret")

    with pytest.raises(stripe.error.SignatureVerificationError):
        stripe_service.verify_webhook_signature(payload, bad_signature)


def test_verify_webhook_signature_tampered_payload(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = _event_payload("checkout.session.completed")
    signature = _sign_payload(payload, WEBHOOK_SECRET)
    tampered_payload = _event_payload("customer.subscription.deleted")

    with pytest.raises(stripe.error.SignatureVerificationError):
        stripe_service.verify_webhook_signature(tampered_payload, signature)


def test_verify_webhook_signature_requires_secret(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    payload = _event_payload("checkout.session.completed")

    with pytest.raises(RuntimeError):
        stripe_service.verify_webhook_signature(payload, "t=1,v1=abc")
