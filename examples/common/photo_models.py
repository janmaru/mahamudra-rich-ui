from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PhotoResource:
    title: str
    published: str | None = None
    page_url: str | None = None
    image_url: str | None = None
    local_path: Path | None = None

