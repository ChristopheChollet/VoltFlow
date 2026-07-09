"""Billing sync logic — Supabase client is mocked (no live DB calls)."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import billing


def test_plan_from_status_active_and_trialing_are_pro():
    assert billing.plan_from_status("active") == billing.PLAN_PRO
    assert billing.plan_from_status("trialing") == billing.PLAN_PRO


def test_plan_from_status_other_statuses_are_free():
    assert billing.plan_from_status("canceled") == billing.PLAN_FREE
    assert billing.plan_from_status("incomplete_expired") == billing.PLAN_FREE
    assert billing.plan_from_status("past_due") == billing.PLAN_FREE


def test_upsert_subscription_from_checkout_requires_org_id():
    with pytest.raises(ValueError):
        billing.upsert_subscription_from_checkout({"customer": "cus_1"})


def test_upsert_subscription_from_checkout_writes_pro_plan():
    fake_client = MagicMock()

    with patch("app.services.billing.get_supabase", return_value=fake_client):
        row = billing.upsert_subscription_from_checkout(
            {
                "client_reference_id": "org-1",
                "customer": "cus_1",
                "subscription": "sub_1",
            }
        )

    assert row["org_id"] == "org-1"
    assert row["plan"] == billing.PLAN_PRO
    assert row["status"] == "active"
    fake_client.table.assert_called_with("subscriptions")
    fake_client.table.return_value.upsert.assert_called_once()
    args, kwargs = fake_client.table.return_value.upsert.call_args
    assert args[0]["stripe_customer_id"] == "cus_1"
    assert kwargs["on_conflict"] == "org_id"


def test_upsert_subscription_from_stripe_subscription_downgrades_on_cancel():
    fake_client = MagicMock()

    with patch("app.services.billing.get_supabase", return_value=fake_client):
        row = billing.upsert_subscription_from_stripe_subscription(
            {"id": "sub_1", "customer": "cus_1", "status": "canceled"}
        )

    assert row["plan"] == billing.PLAN_FREE
    assert row["status"] == "canceled"
    fake_client.table.return_value.update.return_value.eq.assert_called_with(
        "stripe_customer_id", "cus_1"
    )


def test_record_usage_inserts_dynamic_pricing(monkeypatch):
    fake_table = MagicMock()
    fake_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    fake_table.insert.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "line-1",
                "amount_cents": 120,
                "pricing_source": "gridpulse_carbon",
            }
        ]
    )
    fake_client = MagicMock()
    fake_client.table.return_value = fake_table

    slot = {
        "id": "slot-1",
        "org_id": "org-1",
        "power_kw": 5,
        "start_at": "2026-01-06T09:00:00+00:00",
        "end_at": "2026-01-06T10:00:00+00:00",
        "gridpulse_score": None,
    }

    with patch("app.services.billing.get_supabase", return_value=fake_client):
        with patch("app.services.billing._get_flex_slot", return_value=slot):
            with patch(
                "app.services.billing.compute_line_pricing",
                return_value={
                    "amount_cents": 120,
                    "kwh": 5.0,
                    "duration_hours": 1.0,
                    "unit_price_cents": 24,
                    "pricing_source": "gridpulse_carbon",
                    "carbon_gco2_kwh": 70.0,
                    "hp_hc_band": "HP",
                },
            ):
                result = billing.record_usage("org-1", "slot-1")

    assert result["id"] == "line-1"
    fake_table.insert.assert_called_once()


def test_record_usage_is_idempotent_for_same_slot():
    existing = {"id": "line-existing", "flex_slot_id": "slot-1", "amount_cents": 50}

    with patch("app.services.billing._get_existing_line", return_value=existing):
        result = billing.record_usage("org-1", "slot-1")

    assert result == existing


def test_is_org_pro_true_when_active(monkeypatch):
    with patch(
        "app.services.billing.get_subscription",
        return_value={"plan": billing.PLAN_PRO, "status": "active"},
    ):
        assert billing.is_org_pro("org-1") is True


def test_is_org_pro_false_when_no_subscription():
    with patch("app.services.billing.get_subscription", return_value=None):
        assert billing.is_org_pro("org-1") is False
