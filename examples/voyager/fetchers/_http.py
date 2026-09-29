from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10


def http_json(url: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.warning("HTTP GET %s failed: %s", url, exc)
        return None
    except ValueError as exc:
        logger.warning("Non-JSON response from %s: %s", url, exc)
        return None


def http_text(url: str, params: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str | None:
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("HTTP GET %s failed: %s", url, exc)
        return None


def safe_float(value: Any) -> float | None:
    if value is None or value == "" or value == "null":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
