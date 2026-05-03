from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from examples.voyager.fetchers._http import http_json, safe_float

KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
PLASMA_URL = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
MAG_URL = "https://services.swpc.noaa.gov/products/solar-wind/mag-5-minute.json"
SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"

INTERVAL_SECONDS = 300


def fetch_weather() -> tuple[list[dict[str, str]], dict[str, Any]]:
    kp = _fetch_kp()
    speed, density, temperature, bz = _fetch_solar_wind()
    g, s, r = _fetch_scales()

    records: list[dict[str, str]] = [
        {"Metric": "Kp Index", "Value": _format_optional(kp, "{:.2f}")},
        {"Metric": "NOAA Scales", "Value": f"G{g} S{s} R{r}"},
        {"Metric": "Wind Speed", "Value": _format_optional(speed, "{:.1f} km/s")},
        {"Metric": "Wind Density", "Value": _format_optional(density, "{:.2f} p/cm^3")},
        {"Metric": "IMF Bz", "Value": _format_optional(bz, "{:+.2f} nT")},
        {"Metric": "Wind Temp", "Value": _format_optional(temperature, "{:,.0f} K")},
    ]
    sync = {
        "source": "NOAA SWPC",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": INTERVAL_SECONDS,
    }
    return records, sync


def _fetch_kp() -> float | None:
    payload = http_json(KP_URL)
    if not isinstance(payload, list) or not payload:
        return None
    last = payload[-1]
    if isinstance(last, dict):
        return safe_float(last.get("Kp"))
    if isinstance(last, list) and len(last) >= 2:
        return safe_float(last[1])
    return None


def _fetch_solar_wind() -> tuple[float | None, float | None, float | None, float | None]:
    plasma = http_json(PLASMA_URL)
    mag = http_json(MAG_URL)
    speed = density = temperature = bz = None
    if isinstance(plasma, list) and len(plasma) >= 2:
        last = plasma[-1]
        if isinstance(last, list) and len(last) >= 4:
            density = safe_float(last[1])
            speed = safe_float(last[2])
            temperature = safe_float(last[3])
    if isinstance(mag, list) and len(mag) >= 2:
        last = mag[-1]
        if isinstance(last, list) and len(last) >= 4:
            bz = safe_float(last[3])
    return speed, density, temperature, bz


def _fetch_scales() -> tuple[int, int, int]:
    payload = http_json(SCALES_URL)
    if not isinstance(payload, dict):
        return 0, 0, 0
    current = payload.get("0")
    if not isinstance(current, dict):
        return 0, 0, 0
    return _scale_value(current, "G"), _scale_value(current, "S"), _scale_value(current, "R")


def _scale_value(current: dict[str, Any], key: str) -> int:
    entry = current.get(key)
    if not isinstance(entry, dict):
        return 0
    raw = entry.get("Scale")
    try:
        return int(raw) if raw is not None else 0
    except (ValueError, TypeError):
        return 0


def _format_optional(value: float | None, pattern: str) -> str:
    return pattern.format(value) if value is not None else "N/A"
