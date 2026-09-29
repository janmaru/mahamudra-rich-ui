from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from rich.console import Console

from examples.common.photo_models import PhotoResource
from examples.voyager.fetchers import (
    fetch_alerts,
    fetch_dsn,
    fetch_photo,
    fetch_spacecraft,
    fetch_trajectory,
    fetch_weather,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(r"C:\Coding\Voyager-Explorer\cache")


def build_voyager_from_cache(
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Compatibility entry point. The example now goes live, so ``cache_dir`` is ignored."""
    return build_voyager_payload()


def build_voyager_photo_resource(cache_dir: Path = DEFAULT_CACHE_DIR) -> PhotoResource | None:
    """Return a local PhotoResource if the legacy Voyager-Explorer cache is present."""
    photo_meta = cache_dir / "photo_meta.json"
    photo_bin = cache_dir / "photo.bin"
    if not photo_meta.exists() or not photo_bin.exists():
        return None
    try:
        meta = json.loads(photo_meta.read_text(encoding="utf-8"))
    except Exception:
        return None
    return PhotoResource(
        title=meta.get("title", "Untitled photo"),
        published=meta.get("published"),
        page_url=meta.get("url"),
        image_url=meta.get("image_url"),
        local_path=photo_bin,
    )


def build_voyager_payload() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = _build_spec()
    sync: dict[str, Any] = {}
    data: dict[str, Any] = {}
    console = Console(stderr=True)

    spacecraft_records, mission_items, spacecraft_sync = _run_step(
        console, "Fetching spacecraft state (JPL Horizons)", fetch_spacecraft,
    )
    data["spacecraft"] = spacecraft_records
    data["mission"] = mission_items
    sync["spacecraft"] = spacecraft_sync
    sync["mission"] = spacecraft_sync

    dsn_records, dsn_sync = _run_step(
        console, "Fetching DSN communications", fetch_dsn,
    )
    data["dsn"] = dsn_records
    sync["dsn"] = dsn_sync

    weather_records, weather_sync = _run_step(
        console, "Fetching space weather", fetch_weather,
    )
    data["weather"] = weather_records
    sync["weather"] = weather_sync

    alerts_items, alerts_sync = _run_step(
        console, "Fetching alerts", fetch_alerts,
    )
    data["alerts"] = alerts_items
    sync["alerts"] = alerts_sync

    trajectory_payload, trajectory_sync = _run_step(
        console, "Fetching trajectory (JPL Horizons)", fetch_trajectory,
    )
    data["trajectory"] = trajectory_payload
    sync["trajectory"] = trajectory_sync

    photo_data, photo_sync = _run_step(
        console, "Fetching NASA photo metadata", fetch_photo,
    )
    if photo_data is None:
        console.print("[yellow]![/yellow] NASA photo unavailable, using placeholder")
        data["photo"] = {
            "title": "NASA Images unavailable",
            "published": None,
            "url": None,
            "image_url": None,
        }
    else:
        data["photo"] = photo_data
        if photo_sync is not None:
            sync["photo"] = photo_sync

    data["update"] = _build_update_items(sync)
    sync["update"] = {
        "source": "Voyager live adapter",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "interval_seconds": 5,
    }
    return spec, data, sync


def _run_step(console: Console, label: str, fn: Callable[[], T]) -> T:
    start = time.monotonic()
    with console.status(f"[cyan]{label}...[/cyan]", spinner="dots"):
        result = fn()
    elapsed = time.monotonic() - start
    console.print(f"[green]\u2713[/green] {label} [dim]({elapsed:.1f}s)[/dim]")
    return result


def _build_spec() -> dict[str, Any]:
    return {
        "type": "frame",
        "title": "Voyager Explorer",
        "slots": {
            "header": [
                {"type": "panel", "title": "Mission", "bind": "mission"}
            ],
            "body": [
                {
                    "type": "stack",
                    "direction": "row",
                    "layout": {"equal_height": True},
                    "responsive": {"sm": "column", "md": "row", "lg": "row"},
                    "children": [
                        {
                            "type": "table",
                            "title": "Spacecraft",
                            "bind": "spacecraft",
                            "layout": {
                                "span": {"sm": 12, "md": 12, "lg": 6},
                                "min_width": 60,
                            },
                        },
                        {
                            "type": "table",
                            "title": "DSN Communications",
                            "bind": "dsn",
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 3},
                                "min_width": 34,
                            },
                        },
                        {
                            "type": "panel",
                            "title": "Update",
                            "bind": "update",
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 3},
                                "min_width": 34,
                            },
                        },
                    ],
                },
                {
                    "type": "stack",
                    "direction": "row",
                    "layout": {"equal_height": True},
                    "responsive": {"sm": "column", "md": "row", "lg": "row"},
                    "children": [
                        {
                            "type": "table",
                            "title": "Space Weather",
                            "bind": "weather",
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 6},
                                "min_width": 36,
                            },
                        },
                        {
                            "type": "panel",
                            "title": "Alerts & Events",
                            "bind": "alerts",
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 6},
                                "min_width": 36,
                            },
                        },
                    ],
                },
                {
                    "type": "stack",
                    "direction": "row",
                    "layout": {"equal_height": True},
                    "responsive": {"sm": "column", "md": "row", "lg": "row"},
                    "children": [
                        {
                            "type": "scatter_2d",
                            "title": "Trajectory",
                            "bind": "trajectory",
                            "options": {"plane": "auto"},
                            "actions": [
                                {
                                    "id": "open_scatter",
                                    "label": "open trajectory viewer",
                                    "key": "R",
                                }
                            ],
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 6},
                                "min_width": 40,
                            },
                        },
                        {
                            "type": "photo_card",
                            "title": "NASA Photo",
                            "bind": "photo",
                            "options": {
                                "mode": "native_hint",
                                "hint": "Best viewed in the Voyager native photo viewer",
                            },
                            "actions": [
                                {
                                    "id": "open_photo",
                                    "label": "open photo viewer",
                                    "key": "T",
                                }
                            ],
                            "layout": {
                                "span": {"sm": 12, "md": 6, "lg": 6},
                                "min_width": 40,
                            },
                        },
                    ],
                },
            ],
        },
    }


def _build_update_items(sync: dict[str, Any]) -> list[str]:
    titles = {
        "mission": "Mission",
        "spacecraft": "Spacecraft",
        "dsn": "DSN",
        "weather": "Weather",
        "alerts": "Alerts",
        "trajectory": "Trajectory",
        "photo": "Photo",
    }
    items: list[str] = []
    for bind, title in titles.items():
        meta = sync.get(bind)
        if not meta:
            items.append(f"{title} | awaiting fetcher")
            continue
        parts = [title]
        if meta.get("interval_seconds") is not None:
            parts.append(f"every {meta['interval_seconds']}s")
        items.append(" | ".join(parts))
    return items
