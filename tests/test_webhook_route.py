"""End-to-end test of POST /webhooks/stripe — catches StripeObject/dict mismatches
that unit tests on individual functions can miss (see billing.py upsert functions,
which expect plain dicts, while Stripe's SDK delivers StripeObject instances)."""

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

WEBHOOK_SECRET = "whsec_test_secret"


def _sign(payload: bytes, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _checkout_completed_payload() -> bytes:
    return json.dumps(
        {
            "id": "evt_1",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "object": "checkout.session",
                    "client_reference_id": "org-abc",
                    "customer": "cus_1",
                    "subscription": "sub_1",
                }
            },
        }
    ).encode()


def _subscription_updated_payload(status: str = "active") -> bytes:
    return json.dumps(
        {
            "id": "evt_2",
            "object": "event",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_1",
                    "object": "subscription",
                    "customer": "cus_1",
                    "status": status,
                    "current_period_end": 1735689600,
                }
            },
        }
    ).encode()


def test_webhook_checkout_completed_returns_200(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = _checkout_completed_payload()
    signature = _sign(payload, WEBHOOK_SECRET)

    fake_client = MagicMock()
    with patch("app.services.billing.get_supabase", return_value=fake_client):
        client = TestClient(app)
        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    assert response.json() == {"received": True}
    fake_client.table.assert_called_with("subscriptions")
    args, kwargs = fake_client.table.return_value.upsert.call_args
    assert args[0]["org_id"] == "org-abc"
    assert args[0]["stripe_customer_id"] == "cus_1"
    assert kwargs["on_conflict"] == "org_id"


def test_webhook_subscription_updated_returns_200(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = _subscription_updated_payload(status="active")
    signature = _sign(payload, WEBHOOK_SECRET)

    fake_client = MagicMock()
    with patch("app.services.billing.get_supabase", return_value=fake_client):
        client = TestClient(app)
        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    fake_client.table.return_value.update.assert_called_once()
    args, _ = fake_client.table.return_value.update.call_args
    assert args[0]["plan"] == "pro"
    assert args[0]["status"] == "active"


def test_webhook_subscription_deleted_downgrades_to_free(monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    payload = json.dumps(
        {
            "id": "evt_3",
            "object": "event",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_1",
                    "object": "subscription",
                    "customer": "cus_1",
                    "status": "canceled",
                }
            },
        }
    ).encode()
    signature = _sign(payload, WEBHOOK_SECRET)

    fake_client = MagicMock()
    with patch("app.services.billing.get_supabase", return_value=fake_client):
        client = TestClient(app)
        response = client.post(
            "/webhooks/stripe",
            content=payload,
            headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
        )

    assert response.status_code == 200
    args, _ = fake_client.table.return_value.update.call_args
    assert args[0]["plan"] == "free"
