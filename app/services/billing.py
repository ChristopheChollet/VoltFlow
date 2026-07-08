"""Sync Stripe subscription state to Supabase + record stub usage billing lines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.db.client import get_supabase

PLAN_FREE = "free"
PLAN_PRO = "pro"

ACTIVE_STATUSES = {"active", "trialing"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def plan_from_status(status: str) -> str:
    return PLAN_PRO if status in ACTIVE_STATUSES else PLAN_FREE


def upsert_subscription_from_checkout(session: dict[str, Any]) -> dict[str, Any]:
    """Handle `checkout.session.completed` — link org_id <-> stripe_customer_id."""
    org_id = session.get("client_reference_id") or (session.get("metadata") or {}).get(
        "org_id"
    )
    if not org_id:
        raise ValueError("checkout.session.completed missing client_reference_id/org_id")

    client = get_supabase()
    row = {
        "org_id": org_id,
        "stripe_customer_id": session.get("customer"),
        "stripe_subscription_id": session.get("subscription"),
        "plan": PLAN_PRO,
        "status": "active",
        "updated_at": _now_iso(),
    }
    client.table("subscriptions").upsert(row, on_conflict="org_id").execute()
    return row


def upsert_subscription_from_stripe_subscription(subscription: dict[str, Any]) -> dict[str, Any]:
    """Handle `customer.subscription.updated` / `customer.subscription.deleted`."""
    client = get_supabase()
    stripe_customer_id = subscription.get("customer")
    status = subscription.get("status", "canceled")
    plan = plan_from_status(status)

    current_period_end = subscription.get("current_period_end")
    period_end_iso = (
        datetime.fromtimestamp(current_period_end, tz=timezone.utc).isoformat()
        if current_period_end
        else None
    )

    row = {
        "stripe_subscription_id": subscription.get("id"),
        "plan": plan,
        "status": status,
        "current_period_end": period_end_iso,
        "updated_at": _now_iso(),
    }
    client.table("subscriptions").update(row).eq(
        "stripe_customer_id", stripe_customer_id
    ).execute()
    return {**row, "stripe_customer_id": stripe_customer_id}


def get_subscription(org_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    resp = (
        client.table("subscriptions").select("*").eq("org_id", org_id).limit(1).execute()
    )
    return resp.data[0] if resp.data else None


def is_org_pro(org_id: str) -> bool:
    sub = get_subscription(org_id)
    if not sub:
        return False
    return sub.get("plan") == PLAN_PRO and sub.get("status") in ACTIVE_STATUSES


def record_usage(org_id: str, flex_slot_id: str | None) -> dict[str, Any]:
    """Insert a stub billing line for a flex_slot (V1: fixed amount, test mode)."""
    settings = get_settings()
    amount_cents = int(settings.get("usage_stub_amount_cents") or 50)

    client = get_supabase()
    row = {
        "org_id": org_id,
        "flex_slot_id": flex_slot_id,
        "amount_cents": amount_cents,
        "created_at": _now_iso(),
    }
    resp = client.table("billing_lines").insert(row).execute()
    return resp.data[0] if resp.data else row
