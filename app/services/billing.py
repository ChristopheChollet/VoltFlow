"""Sync Stripe subscription state to Supabase + record usage billing lines (V2 dynamic pricing)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.db.client import get_supabase
from app.services.pricing import compute_line_pricing

PLAN_FREE = "free"
PLAN_PRO = "pro"

ACTIVE_STATUSES = {"active", "trialing"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_bounds(month: str | None) -> tuple[str | None, str | None]:
    if not month:
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start.isoformat(), end.isoformat()

    try:
        year_str, month_str = month.split("-", 1)
        year = int(year_str)
        mon = int(month_str)
        start = datetime(year, mon, 1, tzinfo=timezone.utc)
        if mon == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, mon + 1, 1, tzinfo=timezone.utc)
        return start.isoformat(), end.isoformat()
    except (ValueError, TypeError):
        return _month_bounds(None)


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


def _get_flex_slot(flex_slot_id: str | None) -> dict[str, Any] | None:
    if not flex_slot_id:
        return None
    client = get_supabase()
    resp = (
        client.table("flex_slots")
        .select(
            "id, org_id, power_kw, start_at, end_at, gridpulse_score, source, kind, status"
        )
        .eq("id", flex_slot_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _get_existing_line(flex_slot_id: str | None) -> dict[str, Any] | None:
    if not flex_slot_id:
        return None
    client = get_supabase()
    resp = (
        client.table("billing_lines")
        .select("*")
        .eq("flex_slot_id", flex_slot_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def record_usage(org_id: str, flex_slot_id: str | None) -> dict[str, Any]:
    """Insert a billing line for a flex_slot (V2: dynamic pricing, idempotent per slot)."""
    existing = _get_existing_line(flex_slot_id)
    if existing:
        return existing

    slot = _get_flex_slot(flex_slot_id)
    if slot and slot.get("org_id") != org_id:
        raise ValueError("flex_slot does not belong to org")

    pricing = compute_line_pricing(slot)
    client = get_supabase()
    row = {
        "org_id": org_id,
        "flex_slot_id": flex_slot_id,
        "amount_cents": pricing["amount_cents"],
        "kwh": pricing["kwh"],
        "duration_hours": pricing["duration_hours"],
        "unit_price_cents": pricing["unit_price_cents"],
        "pricing_source": pricing["pricing_source"],
        "carbon_gco2_kwh": pricing["carbon_gco2_kwh"],
        "hp_hc_band": pricing["hp_hc_band"],
        "created_at": _now_iso(),
    }
    resp = client.table("billing_lines").insert(row).execute()
    return resp.data[0] if resp.data else row


def list_billing_lines(
    org_id: str,
    *,
    month: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    start_iso, end_iso = _month_bounds(month)
    client = get_supabase()
    query = (
        client.table("billing_lines")
        .select(
            "id, org_id, flex_slot_id, amount_cents, kwh, duration_hours, "
            "unit_price_cents, pricing_source, carbon_gco2_kwh, hp_hc_band, created_at"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 200)))
    )
    if start_iso and end_iso:
        query = query.gte("created_at", start_iso).lt("created_at", end_iso)
    resp = query.execute()
    return resp.data or []


def get_usage_summary(org_id: str, *, month: str | None = None) -> dict[str, Any]:
    lines = list_billing_lines(org_id, month=month, limit=200)
    total_cents = sum(int(line.get("amount_cents") or 0) for line in lines)
    total_kwh = round(
        sum(float(line.get("kwh") or 0) for line in lines if line.get("kwh") is not None),
        3,
    )
    start_iso, end_iso = _month_bounds(month)
    return {
        "org_id": org_id,
        "month": month or datetime.now(timezone.utc).strftime("%Y-%m"),
        "period_start": start_iso,
        "period_end": end_iso,
        "line_count": len(lines),
        "total_cents": total_cents,
        "total_kwh": total_kwh,
    }
