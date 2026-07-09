"""V2 dynamic pricing — flex_slot consumption × carbon signal × HP/HC band."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings

DEFAULT_POWER_KW = 10.0
MIN_DURATION_HOURS = 0.25
BASE_PRICE_CENTS_PER_KWH = 12  # 0.12 €/kWh reference (simplified, not regulatory)

PRICING_GRIDPULSE = "gridpulse_carbon"
PRICING_SLOT_SCORE = "slot_score_fallback"
PRICING_STUB = "stub_fallback"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def slot_duration_hours(start_at: str | None, end_at: str | None) -> float:
    start = _parse_iso(start_at)
    end = _parse_iso(end_at)
    if not start or not end:
        return MIN_DURATION_HOURS
    hours = (end - start).total_seconds() / 3600
    return max(MIN_DURATION_HOURS, round(hours, 3))


def hp_hc_band(start_at: str | None) -> tuple[str, float]:
    """Simplified French HP/HC band (weekday 08:00–20:00 Europe/Paris = HP)."""
    start = _parse_iso(start_at)
    if not start:
        return "HC", 0.85
    local = start.astimezone(ZoneInfo("Europe/Paris"))
    if local.weekday() < 5 and 8 <= local.hour < 20:
        return "HP", 1.15
    return "HC", 0.85


def carbon_multiplier(carbon_gco2_kwh: float | None) -> float:
    if carbon_gco2_kwh is None:
        return 1.0
    if carbon_gco2_kwh <= 80:
        return 0.75
    if carbon_gco2_kwh <= 200:
        return 1.0
    return 1.25


def score_to_carbon_proxy(score: float | None) -> float | None:
    """Map GridPulse window score (0–100, higher = greener) to a carbon proxy."""
    if score is None:
        return None
    clamped = max(0.0, min(100.0, float(score)))
    return round(250 - clamped * 2.0, 1)


def fetch_carbon_at_slot_start(start_at: str | None) -> float | None:
    settings = get_settings()
    base_url = (settings.get("gridpulse_api_url") or "").rstrip("/")
    if not base_url or not start_at:
        return None

    target = _parse_iso(start_at)
    if not target:
        return None

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{base_url}/api/v1/carbon", params={"hours": 48})
            response.raise_for_status()
            points = response.json().get("points") or []
    except (httpx.HTTPError, ValueError, TypeError):
        return None

    best: tuple[float, float] | None = None
    for point in points:
        recorded = _parse_iso(point.get("recorded_at"))
        carbon = point.get("carbon_gco2_kwh")
        if recorded is None or carbon is None:
            continue
        delta = abs((recorded - target).total_seconds())
        if best is None or delta < best[0]:
            best = (delta, float(carbon))

    return best[1] if best else None


def compute_line_pricing(slot: dict[str, Any] | None) -> dict[str, Any]:
    """Return pricing fields for a billing_lines insert."""
    settings = get_settings()
    stub_cents = int(settings.get("usage_stub_amount_cents") or 50)
    base_cents = int(settings.get("base_price_cents_per_kwh") or BASE_PRICE_CENTS_PER_KWH)

    if not slot:
        return {
            "amount_cents": stub_cents,
            "kwh": None,
            "duration_hours": None,
            "unit_price_cents": None,
            "pricing_source": PRICING_STUB,
            "carbon_gco2_kwh": None,
            "hp_hc_band": None,
        }

    duration_hours = slot_duration_hours(slot.get("start_at"), slot.get("end_at"))
    power_kw = float(slot.get("power_kw") or DEFAULT_POWER_KW)
    kwh = round(power_kw * duration_hours, 3)

    band_label, band_mult = hp_hc_band(slot.get("start_at"))

    carbon = fetch_carbon_at_slot_start(slot.get("start_at"))
    pricing_source = PRICING_GRIDPULSE
    if carbon is None and slot.get("gridpulse_score") is not None:
        carbon = score_to_carbon_proxy(slot.get("gridpulse_score"))
        pricing_source = PRICING_SLOT_SCORE
    if carbon is None:
        carbon_mult = 1.0
        pricing_source = PRICING_STUB
    else:
        carbon_mult = carbon_multiplier(carbon)

    unit_price_cents = max(1, round(base_cents * carbon_mult * band_mult))
    amount_cents = max(1, round(kwh * unit_price_cents))

    if pricing_source == PRICING_STUB and kwh <= 0:
        return {
            "amount_cents": stub_cents,
            "kwh": kwh or None,
            "duration_hours": duration_hours,
            "unit_price_cents": stub_cents,
            "pricing_source": PRICING_STUB,
            "carbon_gco2_kwh": None,
            "hp_hc_band": band_label,
        }

    return {
        "amount_cents": amount_cents,
        "kwh": kwh,
        "duration_hours": duration_hours,
        "unit_price_cents": unit_price_cents,
        "pricing_source": pricing_source,
        "carbon_gco2_kwh": carbon,
        "hp_hc_band": band_label,
    }
