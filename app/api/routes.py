from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import get_settings
from app.services import billing, stripe_service

router = APIRouter(tags=["billing"])


def _check_service_key(provided: str | None) -> None:
    secret = (get_settings().get("voltflow_integration_secret") or "").strip()
    if not secret:
        return
    if (provided or "").strip() != secret:
        raise HTTPException(status_code=401, detail="Invalid service key")


@router.post("/checkout/session")
def post_checkout_session(
    body: dict[str, Any],
    x_voltflow_service_key: str | None = Header(default=None, alias="X-VoltFlow-Service-Key"),
) -> dict[str, str]:
    _check_service_key(x_voltflow_service_key)
    org_id = body.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")

    try:
        url = stripe_service.create_checkout_session(org_id, customer_email=body.get("email"))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"url": url}


@router.post("/billing/portal")
def post_billing_portal(
    body: dict[str, Any],
    x_voltflow_service_key: str | None = Header(default=None, alias="X-VoltFlow-Service-Key"),
) -> dict[str, str]:
    _check_service_key(x_voltflow_service_key)
    org_id = body.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")

    subscription = billing.get_subscription(org_id)
    stripe_customer_id = subscription.get("stripe_customer_id") if subscription else None
    if not stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer for this org")

    try:
        url = stripe_service.create_billing_portal_session(stripe_customer_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"url": url}


@router.get("/api/v1/subscriptions/{org_id}")
def get_subscription_status(
    org_id: str,
    x_voltflow_service_key: str | None = Header(default=None, alias="X-VoltFlow-Service-Key"),
) -> dict[str, Any]:
    _check_service_key(x_voltflow_service_key)
    subscription = billing.get_subscription(org_id)
    if subscription:
        return subscription
    return {"org_id": org_id, "plan": billing.PLAN_FREE, "status": "none"}


@router.post("/usage/record")
def post_usage_record(
    body: dict[str, Any],
    x_voltflow_service_key: str | None = Header(default=None, alias="X-VoltFlow-Service-Key"),
) -> dict[str, Any]:
    _check_service_key(x_voltflow_service_key)
    org_id = body.get("org_id")
    flex_slot_id = body.get("flex_slot_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")
    if not billing.is_org_pro(org_id):
        raise HTTPException(status_code=402, detail="Org is not on the Pro plan")
    return billing.record_usage(org_id, flex_slot_id)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, bool]:
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe_service.verify_webhook_signature(payload, stripe_signature)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid signature: {exc}") from exc

    event_type = event["type"]
    # Newer stripe-python versions no longer make StripeObject dict-like
    # (no .get()) — convert explicitly so billing.py can use plain dict access.
    data_object = event["data"]["object"].to_dict()

    if event_type == "checkout.session.completed":
        billing.upsert_subscription_from_checkout(data_object)
    elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
        billing.upsert_subscription_from_stripe_subscription(data_object)

    return {"received": True}
