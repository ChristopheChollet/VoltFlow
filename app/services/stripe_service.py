"""Stripe SDK wrapper — checkout sessions, billing portal, webhook verification."""

from __future__ import annotations

from typing import Any

import stripe

from app.config import get_settings


def _configured_stripe() -> Any:
    settings = get_settings()
    api_key = settings.get("stripe_secret_key")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY is required")
    stripe.api_key = api_key
    return stripe


def create_checkout_session(org_id: str, customer_email: str | None = None) -> str:
    """Create a Stripe Checkout Session (subscription mode) for an org.

    `client_reference_id` carries the GreenOps org_id so the webhook can
    link the resulting Stripe customer back to the right organization.
    """
    client = _configured_stripe()
    settings = get_settings()
    price_id = settings.get("stripe_price_id_pro")
    if not price_id:
        raise RuntimeError("STRIPE_PRICE_ID_PRO is required")

    session = client.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        client_reference_id=org_id,
        customer_email=customer_email,
        success_url=settings["checkout_success_url"],
        cancel_url=settings["checkout_cancel_url"],
        metadata={"org_id": org_id},
    )
    return session.url


def create_billing_portal_session(stripe_customer_id: str) -> str:
    client = _configured_stripe()
    settings = get_settings()

    session = client.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=settings["billing_portal_return_url"],
    )
    return session.url


def verify_webhook_signature(payload: bytes, signature: str) -> Any:
    """Verify a Stripe webhook signature and return the parsed event.

    Raises `stripe.error.SignatureVerificationError` on invalid signature.
    """
    settings = get_settings()
    webhook_secret = settings.get("stripe_webhook_secret")
    if not webhook_secret:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is required")
    return stripe.Webhook.construct_event(payload, signature, webhook_secret)
