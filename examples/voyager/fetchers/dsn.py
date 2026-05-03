from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from examples.voyager.fetchers._http import http_text, safe_float

URL = "https://eyes.nasa.gov/dsn/data/dsn.xml"
INTERVAL_SECONDS = 10

VOYAGER_DSN_CODES = ("VGR1", "VGR2")

STATIONS = {
    "gdscc": "Goldstone",
    "mdscc": "Madrid",
    "cdscc": "Canberra",
}

DISH_SIZES = {
    "DSS14": 70, "DSS43": 70, "DSS63": 70,
    "DSS35": 34, "DSS36": 34, "DSS34": 34,
    "DSS24": 34, "DSS25": 34, "DSS26": 34,
    "DSS54": 34, "DSS55": 34, "DSS65": 34,
}


def fetch_dsn() -> tuple[list[dict[str, str]], dict[str, Any]]:
    xml_text = http_text(URL)
    records: list[dict[str, str]] = []
    if xml_text:
        try:
            root = ET.fromstring(xml_text)
            records = list(_extract_records(root))
        except ET.ParseError:
            records = []
    if not records:
        records = [
            {"Probe": "-", "Station": "No active DSN link", "Dish": "-", "Down": "-", "Up": "-", "RTLT": "-", "Range": "-"}
        ]
    sync = {
        "source": "NASA Eyes DSN",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": INTERVAL_SECONDS,
    }
    return records, sync


def _extract_records(root: ET.Element):
    current_station = ""
    for child in root:
        if child.tag == "station":
            code = child.get("name", "")
            current_station = STATIONS.get(code, code)
            continue
        if child.tag != "dish":
            continue
        dish = child
        dish_name = (dish.get("name") or "").upper()
        size = DISH_SIZES.get(dish_name, 34)
        for target_code in VOYAGER_DSN_CODES:
            tracking, rtlt, downleg_range = _extract_target(dish, target_code)
            if not tracking:
                continue
            down_freq, down_rate = _extract_signal(dish, "downSignal", target_code)
            up_freq, up_rate = _extract_signal(dish, "upSignal", target_code)
            yield {
                "Probe": target_code,
                "Station": current_station,
                "Dish": f"{dish_name} ({size}m)",
                "Down": f"{_format_freq(down_freq)} {_format_rate(down_rate)}",
                "Up": f"{_format_freq(up_freq)} {_format_rate(up_rate)}",
                "RTLT": _format_rtlt(rtlt),
                "Range": (f"{_format_number(downleg_range)} km" if downleg_range else "-"),
            }


def _extract_target(dish: ET.Element, target_code: str) -> tuple[bool, float | None, float | None]:
    for target in dish.findall("target"):
        if target.get("name") == target_code:
            return True, safe_float(target.get("rtlt")), safe_float(target.get("downlegRange"))
    for sig in list(dish.findall("downSignal")) + list(dish.findall("upSignal")):
        if sig.get("spacecraft") == target_code:
            return True, None, None
    return False, None, None


def _extract_signal(dish: ET.Element, tag: str, target_code: str) -> tuple[float | None, float | None]:
    for sig in dish.findall(tag):
        if sig.get("spacecraft") == target_code and sig.get("active") == "true":
            return safe_float(sig.get("frequency")), safe_float(sig.get("dataRate"))
    for sig in dish.findall(tag):
        if sig.get("spacecraft") == target_code:
            return safe_float(sig.get("frequency")), safe_float(sig.get("dataRate"))
    return None, None


def _format_freq(hz: float | None) -> str:
    if hz is None or hz < 1:
        return "-"
    if hz >= 1e9:
        return f"{hz / 1e9:.2f} GHz"
    return f"{hz / 1e6:.1f} MHz"


def _format_rate(bps: float | None) -> str:
    if bps is None or bps < 1:
        return "-"
    if bps >= 1e6:
        return f"{bps / 1e6:.1f} Mbps"
    if bps >= 1e3:
        return f"{bps / 1e3:.0f} kbps"
    return f"{bps:.0f} bps"


def _format_rtlt(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    if seconds >= 3600:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds:.0f}s"


def _format_number(value: float) -> str:
    return f"{value:,.0f}"
