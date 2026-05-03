from __future__ import annotations

import csv
import io
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from examples.voyager.fetchers._http import http_json

logger = logging.getLogger(__name__)

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
HORIZONS_TIMEOUT = 30

VOYAGER_1_SPKID = "-31"
VOYAGER_2_SPKID = "-32"
VOYAGER_1_NAME = "Voyager 1"
VOYAGER_2_NAME = "Voyager 2"
VOYAGER_1_LAUNCH = datetime(1977, 9, 5, 12, 56, 0, tzinfo=timezone.utc)
VOYAGER_2_LAUNCH = datetime(1977, 8, 20, 14, 29, 0, tzinfo=timezone.utc)

SPACECRAFT_INTERVAL_SECONDS = 300
TRAJECTORY_INTERVAL_SECONDS = 3600

EARTH_CENTER = "500@399"
KM_PER_AU = 149_597_870.7
LIGHT_KM_PER_HOUR = 1_079_252_848.8


def fetch_spacecraft() -> tuple[list[dict[str, str]], list[str], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    voyagers = [
        _build_vehicle(VOYAGER_1_SPKID, VOYAGER_1_NAME, VOYAGER_1_LAUNCH, now),
        _build_vehicle(VOYAGER_2_SPKID, VOYAGER_2_NAME, VOYAGER_2_LAUNCH, now),
    ]
    voyagers = [v for v in voyagers if v is not None]

    if not voyagers:
        records = [
            {
                "Probe": "No data",
                "Earth Distance": "-",
                "AU / Light": "-",
                "Speed": "-",
                "Sky Position": "-",
                "Position x10^9 km": "-",
            }
        ]
        mission = ["Awaiting Horizons fetcher..."]
    else:
        records = [
            {
                "Probe": v["name"],
                "Earth Distance": f"{_format_number(v['distance_km'])} km ({_format_number(_km_to_miles(v['distance_km']))} mi)",
                "AU / Light": f"{v['distance_au']:.2f} AU | {_format_light_time(v['light_hours'])}",
                "Speed": f"{v['speed_km_s']:.3f} km/s ({_format_number(v['speed_km_s'] * 3600)} km/h)",
                "Sky Position": _format_ra_dec(v["ra"], v["dec"]),
                "Position x10^9 km": f"{v['x'] / 1e9:+.2f} / {v['y'] / 1e9:+.2f} / {v['z'] / 1e9:+.2f}",
            }
            for v in voyagers
        ]
        mission = [
            " | ".join(
                [
                    v["name"],
                    f"Day {v['days_since_launch']:,}",
                    _format_light_time(v["light_hours"]),
                    _voyager_region(v["distance_au"]),
                ]
            )
            for v in voyagers
        ]

    sync = {
        "source": "JPL Horizons",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": SPACECRAFT_INTERVAL_SECONDS,
    }
    return records, mission, sync


def fetch_trajectory() -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)
    end = now + timedelta(hours=1)
    samples_v1 = _fetch_path(VOYAGER_1_SPKID, start, end)
    samples_v2 = _fetch_path(VOYAGER_2_SPKID, start, end)

    tracks: list[dict[str, Any]] = []
    if samples_v1:
        tracks.append(_build_track(
            label=VOYAGER_1_NAME,
            marker="\u25c6",
            style="bold bright_magenta",
            history_marker="\u00b7",
            history_style="magenta",
            shape="diamond",
            history_shape="dot",
            samples=samples_v1,
        ))
    if samples_v2:
        tracks.append(_build_track(
            label=VOYAGER_2_NAME,
            marker="\u25b2",
            style="bold bright_yellow",
            history_marker="\u00b7",
            history_style="yellow",
            shape="triangle_up",
            history_shape="dot",
            samples=samples_v2,
        ))

    payload: dict[str, Any] = {
        "center": {
            "label": "Earth",
            "marker": "\u25cf",
            "style": "bright_blue",
            "shape": "ringed",
        },
        "tracks": tracks,
    }

    sync = {
        "source": "JPL Horizons (trajectory)",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": TRAJECTORY_INTERVAL_SECONDS,
    }
    return payload, sync


def _build_track(
    label: str,
    marker: str,
    style: str,
    history_marker: str,
    history_style: str,
    shape: str,
    history_shape: str,
    samples: list[tuple[float, float, float, datetime]],
) -> dict[str, Any]:
    if not samples:
        raise ValueError("samples must be a non-empty list")
    sample_points = [{"x": x, "y": y, "z": z} for (x, y, z, _) in samples]
    last_x, last_y, last_z, _ = samples[-1]
    distance_km = math.sqrt(last_x * last_x + last_y * last_y + last_z * last_z)
    distance_au = distance_km / KM_PER_AU
    return {
        "label": label,
        "caption": f"{distance_au:.1f} AU",
        "marker": marker,
        "style": style,
        "history_marker": history_marker,
        "history_style": history_style,
        "shape": shape,
        "history_shape": history_shape,
        "samples": sample_points,
        "current": {"x": last_x, "y": last_y, "z": last_z},
    }


def _build_vehicle(spkid: str, name: str, launch: datetime, now: datetime) -> dict[str, Any] | None:
    state = _fetch_state_vector(spkid, now)
    if state is None:
        return None
    ra, dec = _fetch_observer_data(spkid, now)
    x, y, z, vx, vy, vz = state
    distance_km = math.sqrt(x * x + y * y + z * z)
    speed = math.sqrt(vx * vx + vy * vy + vz * vz)
    return {
        "name": name,
        "x": x,
        "y": y,
        "z": z,
        "vx": vx,
        "vy": vy,
        "vz": vz,
        "distance_km": distance_km,
        "distance_au": distance_km / KM_PER_AU,
        "light_hours": distance_km / LIGHT_KM_PER_HOUR,
        "speed_km_s": speed,
        "ra": ra,
        "dec": dec,
        "days_since_launch": int((now - launch).total_seconds() // 86400),
    }


def _fetch_state_vector(command: str, target_time: datetime) -> tuple[float, float, float, float, float, float] | None:
    start = target_time - timedelta(minutes=5)
    stop = target_time + timedelta(minutes=5)
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": f"'{EARTH_CENTER}'",
        "START_TIME": f"'{start.strftime('%Y-%m-%d %H:%M')}'",
        "STOP_TIME": f"'{stop.strftime('%Y-%m-%d %H:%M')}'",
        "STEP_SIZE": "'1 min'",
        "OUT_UNITS": "KM-S",
        "REF_SYSTEM": "J2000",
        "CSV_FORMAT": "YES",
    }
    payload = http_json(API_URL, params=params, timeout=HORIZONS_TIMEOUT)
    if not isinstance(payload, dict):
        return None
    result_text = payload.get("result")
    if not isinstance(result_text, str):
        return None
    row = _best_csv_row(result_text, target_time)
    if row is None or len(row) < 8:
        return None
    try:
        return (
            float(row[2]), float(row[3]), float(row[4]),
            float(row[5]), float(row[6]), float(row[7]),
        )
    except ValueError:
        return None


def _fetch_observer_data(command: str, target_time: datetime) -> tuple[float | None, float | None]:
    start = target_time - timedelta(minutes=5)
    stop = target_time + timedelta(minutes=5)
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "OBSERVER",
        "CENTER": f"'{EARTH_CENTER}'",
        "START_TIME": f"'{start.strftime('%Y-%m-%d %H:%M')}'",
        "STOP_TIME": f"'{stop.strftime('%Y-%m-%d %H:%M')}'",
        "STEP_SIZE": "'1 min'",
        "QUANTITIES": "'1'",
        "REF_SYSTEM": "ICRF",
        "CSV_FORMAT": "YES",
    }
    payload = http_json(API_URL, params=params, timeout=HORIZONS_TIMEOUT)
    if not isinstance(payload, dict):
        return None, None
    result_text = payload.get("result")
    if not isinstance(result_text, str):
        return None, None
    row = _best_csv_row(result_text, target_time)
    if row is None or len(row) < 5:
        return None, None
    try:
        return float(row[3]), float(row[4])
    except ValueError:
        return None, None


def _fetch_path(command: str, start: datetime, end: datetime) -> list[tuple[float, float, float, datetime]] | None:
    params = {
        "format": "json",
        "COMMAND": f"'{command}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "VECTORS",
        "CENTER": f"'{EARTH_CENTER}'",
        "START_TIME": f"'{start.strftime('%Y-%m-%d %H:%M')}'",
        "STOP_TIME": f"'{end.strftime('%Y-%m-%d %H:%M')}'",
        "STEP_SIZE": "'1 d'",
        "OUT_UNITS": "KM-S",
        "REF_SYSTEM": "J2000",
        "CSV_FORMAT": "YES",
    }
    payload = http_json(API_URL, params=params, timeout=HORIZONS_TIMEOUT)
    if not isinstance(payload, dict):
        return None
    result_text = payload.get("result")
    if not isinstance(result_text, str):
        return None
    rows = _all_csv_rows(result_text)
    points: list[tuple[float, float, float, datetime]] = []
    for fields in rows:
        if len(fields) < 5:
            continue
        try:
            dt = _parse_horizons_date(fields[1])
            points.append((float(fields[2]), float(fields[3]), float(fields[4]), dt))
        except (ValueError, IndexError):
            continue
    return points


def _all_csv_rows(result_text: str) -> list[list[str]]:
    soe_idx = result_text.find("$$SOE")
    eoe_idx = result_text.find("$$EOE")
    if soe_idx == -1 or eoe_idx == -1:
        return []
    block = result_text[soe_idx + 5: eoe_idx].strip()
    rows: list[list[str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        reader = csv.reader(io.StringIO(line))
        rows.append([f.strip() for f in next(reader)])
    return rows


def _best_csv_row(result_text: str, target_time: datetime) -> list[str] | None:
    best_row: list[str] | None = None
    min_diff = float("inf")
    for fields in _all_csv_rows(result_text):
        try:
            dt = _parse_horizons_date(fields[1])
        except (ValueError, IndexError):
            continue
        diff = abs((dt - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            best_row = fields
    return best_row


def _parse_horizons_date(s: str) -> datetime:
    s = s.replace("A.D. ", "").replace("*", "").strip()
    for fmt in (
        "%Y-%b-%d %H:%M:%S.%f",
        "%Y-%b-%d %H:%M:%S",
        "%Y-%b-%d %H:%M",
    ):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse Horizons date: '{s}'")


def _format_number(value: float) -> str:
    return f"{value:,.0f}"


def _km_to_miles(km: float) -> float:
    return km * 0.621371


def _format_light_time(hours: float) -> str:
    if hours >= 1:
        whole_hours = int(hours)
        minutes = int((hours - whole_hours) * 60)
        return f"{whole_hours:02d}h {minutes:02d}m"
    total_minutes = hours * 60
    minutes = int(total_minutes)
    seconds = int((total_minutes - minutes) * 60)
    return f"{minutes:02d}m {seconds:02d}s"


def _format_ra_dec(ra: float | None, dec: float | None) -> str:
    if ra is None or dec is None:
        return "N/A"
    ra_h = ra / 15.0
    h = int(ra_h)
    m = int((ra_h - h) * 60)
    s = int((ra_h - h - m / 60.0) * 3600)
    d = int(abs(dec))
    dm = int((abs(dec) - d) * 60)
    ds = int((abs(dec) - d - dm / 60.0) * 3600)
    sign = "+" if dec >= 0 else "-"
    return f"{h:02d}h {m:02d}m {s:02d}s / {sign}{d:02d}\u00b0 {dm:02d}' {ds:02d}\""


def _voyager_region(distance_au: float) -> str:
    if distance_au > 100:
        return "Interstellar Medium"
    if distance_au > 90:
        return "Heliosheath"
    return "Heliosphere"
