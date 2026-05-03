from __future__ import annotations

import webbrowser
from typing import Protocol

from examples.common.photo_models import PhotoResource
from examples.common.tk_photo_viewer import show_photo_window


class PhotoOpener(Protocol):
    def open(self, photo: PhotoResource) -> None: ...


class TkPhotoOpener:
    def open(self, photo: PhotoResource) -> None:
        show_photo_window(photo)


class BrowserPhotoOpener:
    def open(self, photo: PhotoResource) -> None:
        target = photo.page_url or photo.image_url
        if not target:
            raise RuntimeError("No page_url or image_url is available for this photo.")
        webbrowser.open(target)


def open_photo_with_best_available(photo: PhotoResource) -> None:
    if photo.local_path is not None and photo.local_path.exists():
        try:
            TkPhotoOpener().open(photo)
            return
        except Exception:
            pass
    BrowserPhotoOpener().open(photo)

