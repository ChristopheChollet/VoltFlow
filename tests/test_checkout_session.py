"""Checkout Session + Billing Portal creation — Stripe SDK calls are mocked."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import stripe_service


def test_create_checkout_session_builds_correct_payload(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_123")

    fake_session = MagicMock(url="https://checkout.stripe.com/test-session")

    with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
        url = stripe_service.create_checkout_session("org-abc", customer_email="a@b.com")

    assert url == "https://checkout.stripe.com/test-session"
    _, kwargs = mock_create.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["client_reference_id"] == "org-abc"
    assert kwargs["line_items"] == [{"price": "price_123", "quantity": 1}]
    assert kwargs["customer_email"] == "a@b.com"
    assert kwargs["metadata"] == {"org_id": "org-abc"}


def test_create_checkout_session_requires_secret_key(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("STRIPE_PRICE_ID_PRO", "price_123")

    with pytest.raises(RuntimeError):
        stripe_service.create_checkout_session("org-abc")


def test_create_checkout_session_requires_price_id(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.delenv("STRIPE_PRICE_ID_PRO", raising=False)

    with pytest.raises(RuntimeError):
        stripe_service.create_checkout_session("org-abc")


def test_create_billing_portal_session(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("BILLING_PORTAL_RETURN_URL", "http://localhost:3000/billing")

    fake_session = MagicMock(url="https://billing.stripe.com/test-portal")

    with patch(
        "stripe.billing_portal.Session.create", return_value=fake_session
    ) as mock_create:
        url = stripe_service.create_billing_portal_session("cus_123")

    assert url == "https://billing.stripe.com/test-portal"
    _, kwargs = mock_create.call_args
    assert kwargs["customer"] == "cus_123"
    assert kwargs["return_url"] == "http://localhost:3000/billing"
