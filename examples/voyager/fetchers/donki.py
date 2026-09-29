from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from examples.voyager.fetchers._http import http_json

BASE_URL = "https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/"
EVENT_TYPES = ("FLR", "CME", "GST")
INTERVAL_SECONDS = 900
EVENT_LABELS = {
    "FLR": "Solar Flare",
    "CME": "CME",
    "GST": "Geomagnetic Storm",
}
LOOKBACK_DAYS = 3
MAX_ITEMS = 6


def fetch_alerts() -> tuple[list[str], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    events: list[tuple[str, str]] = []
    for event_type in EVENT_TYPES:
        events.extend(_fetch_event_type(event_type, start, end))
    events.sort(key=lambda pair: pair[1], reverse=True)

    items: list[str] = []
    for label_class, when in events[:MAX_ITEMS]:
        items.append(f"{label_class} | {when}" if when else label_class)
    if not items:
        items = ["No recent alerts or events"]

    sync = {
        "source": "NASA DONKI",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": INTERVAL_SECONDS,
    }
    return items, sync


def _fetch_event_type(event_type: str, start: str, end: str) -> list[tuple[str, str]]:
    payload = http_json(f"{BASE_URL}{event_type}", params={"startDate": start, "endDate": end})
    if not isinstance(payload, list):
        return []
    out: list[tuple[str, str]] = []
    label = EVENT_LABELS.get(event_type, event_type)
    for item in payload:
        if not isinstance(item, dict):
            continue
        if event_type == "FLR":
            when = str(item.get("beginTime") or item.get("peakTime") or "")
            class_type = item.get("classType")
        elif event_type == "CME":
            when = str(item.get("startTime") or "")
            analyses = item.get("cmeAnalyses") or []
            class_type = None
            if analyses and isinstance(analyses[0], dict):
                ha = analyses[0].get("halfAngle")
                class_type = f"HA={ha}" if ha is not None else None
        else:  # GST
            when = str(item.get("startTime") or "")
            kps = item.get("allKpIndex") or []
            class_type = None
            if kps:
                max_kp = max(((k.get("kpIndex") or 0) for k in kps if isinstance(k, dict)), default=0)
                class_type = f"Kp={max_kp}"
        suffix = f" {class_type}" if class_type else ""
        out.append((f"{label}{suffix}", when))
    return out
