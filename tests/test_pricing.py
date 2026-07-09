"""Dynamic pricing engine tests."""

from unittest.mock import MagicMock, patch

from app.services import pricing


def test_slot_duration_hours_minimum():
    assert pricing.slot_duration_hours("2026-01-01T10:00:00+00:00", "2026-01-01T10:05:00+00:00") == 0.25


def test_slot_duration_hours_two_hours():
    hours = pricing.slot_duration_hours(
        "2026-01-01T10:00:00+00:00",
        "2026-01-01T12:00:00+00:00",
    )
    assert hours == 2.0


def test_hp_hc_weekday_peak():
    band, mult = pricing.hp_hc_band("2026-01-06T09:00:00+00:00")  # Tuesday 10:00 Paris
    assert band == "HP"
    assert mult == 1.15


def test_hp_hc_night_offpeak():
    band, mult = pricing.hp_hc_band("2026-01-06T22:00:00+00:00")
    assert band == "HC"
    assert mult == 0.85


def test_carbon_multiplier_green_discount():
    assert pricing.carbon_multiplier(60) == 0.75
    assert pricing.carbon_multiplier(150) == 1.0
    assert pricing.carbon_multiplier(250) == 1.25


def test_compute_line_pricing_with_slot_and_carbon():
    slot = {
        "start_at": "2026-01-06T09:00:00+00:00",
        "end_at": "2026-01-06T11:00:00+00:00",
        "power_kw": 10,
        "gridpulse_score": None,
    }
    with patch("app.services.pricing.fetch_carbon_at_slot_start", return_value=70.0):
        result = pricing.compute_line_pricing(slot)

    assert result["pricing_source"] == pricing.PRICING_GRIDPULSE
    assert result["kwh"] == 20.0
    assert result["duration_hours"] == 2.0
    assert result["hp_hc_band"] == "HP"
    assert result["unit_price_cents"] == 10  # 12 * 0.75 * 1.15 ≈ 10
    assert result["amount_cents"] == 200


def test_compute_line_pricing_stub_without_slot():
    with patch(
        "app.services.pricing.get_settings",
        return_value={"usage_stub_amount_cents": "99", "base_price_cents_per_kwh": "12"},
    ):
        result = pricing.compute_line_pricing(None)
    assert result["pricing_source"] == pricing.PRICING_STUB
    assert result["amount_cents"] == 99


def test_fetch_carbon_at_slot_start_picks_closest_point():
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "points": [
            {"recorded_at": "2026-01-06T08:00:00+00:00", "carbon_gco2_kwh": 180},
            {"recorded_at": "2026-01-06T09:05:00+00:00", "carbon_gco2_kwh": 65},
            {"recorded_at": "2026-01-06T12:00:00+00:00", "carbon_gco2_kwh": 90},
        ]
    }
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get.return_value = fake_response

    with patch("app.services.pricing.get_settings", return_value={"gridpulse_api_url": "https://gp.test"}):
        with patch("app.services.pricing.httpx.Client", return_value=fake_client):
            carbon = pricing.fetch_carbon_at_slot_start("2026-01-06T09:00:00+00:00")

    assert carbon == 65.0
