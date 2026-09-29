from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from examples.voyager.fetchers._http import http_json

API_URL = "https://images-api.nasa.gov/search?q=voyager&media_type=image&keywords=voyager"
INTERVAL_SECONDS = 3600


def fetch_photo() -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    payload = http_json(API_URL)
    if not isinstance(payload, dict):
        return None, None
    items = (payload.get("collection") or {}).get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        meta_list = item.get("data") or []
        links = item.get("links") or []
        if not meta_list:
            continue
        meta = meta_list[0]
        if not isinstance(meta, dict):
            continue
        title = (meta.get("title") or "").strip()
        if not title:
            continue
        nasa_id = (meta.get("nasa_id") or "").strip()
        published = (meta.get("date_created") or "").strip()
        image_url = _extract_image_url(links)
        if not image_url:
            continue
        page_url = f"https://images.nasa.gov/details/{nasa_id}" if nasa_id else image_url

        data = {
            "title": title,
            "published": published or None,
            "url": page_url,
            "image_url": image_url,
        }
        sync = {
            "source": "NASA Images",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "interval_seconds": INTERVAL_SECONDS,
        }
        return data, sync
    return None, None


def _extract_image_url(links: list[Any]) -> str | None:
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("rel") == "preview" and link.get("render") == "image":
            href = link.get("href")
            if isinstance(href, str) and href:
                return href
    for link in links:
        if not isinstance(link, dict):
            continue
        href = link.get("href")
        if isinstance(href, str) and href.lower().endswith((".jpg", ".jpeg", ".png")):
            return href
    return None
