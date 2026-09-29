from __future__ import annotations

import webbrowser
from pathlib import Path

try:
    import tkinter as tk
except ImportError:
    tk = None

from PIL import Image, ImageTk

from examples.common.photo_models import PhotoResource


def show_photo_window(photo: PhotoResource) -> None:
    if tk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")
    if ImageTk is None:
        raise RuntimeError("Pillow ImageTk is not available.")
    if photo.local_path is None or not Path(photo.local_path).exists():
        raise RuntimeError("Local photo file is not available.")

    root = tk.Tk()
    root.title(photo.title)
    root.geometry("1100x760")
    root.configure(bg="#111827")

    header = tk.Frame(root, bg="#020617", height=56)
    header.pack(side=tk.TOP, fill=tk.X)
    tk.Label(
        header,
        text=photo.title,
        font=("Segoe UI", 15, "bold"),
        bg="#020617",
        fg="#7dd3fc",
    ).pack(pady=12)

    body = tk.Frame(root, bg="#111827")
    body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    left = tk.Frame(body, bg="#111827")
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

    right = tk.Frame(body, bg="#111827", width=320)
    right.pack(side=tk.RIGHT, fill=tk.Y)
    right.pack_propagate(False)

    image_label = tk.Label(
        left,
        bg="#000000",
        fg="#cbd5e1",
        text="Loading photo...",
        font=("Segoe UI", 11),
    )
    image_label.pack(fill=tk.BOTH, expand=True)

    image = Image.open(photo.local_path)
    image.thumbnail((760, 620), Image.LANCZOS)
    image_tk = ImageTk.PhotoImage(image)
    image_label.configure(image=image_tk, text="")
    image_label.image = image_tk

    tk.Label(
        right,
        text="PHOTO INFO",
        font=("Segoe UI", 11, "bold"),
        bg="#111827",
        fg="#7dd3fc",
    ).pack(anchor="w", pady=(0, 10))

    info_lines = [f"Title:\n{photo.title}"]
    if photo.published:
        info_lines.append(f"Published:\n{photo.published}")
    if photo.local_path:
        info_lines.append(f"Local file:\n{photo.local_path}")
    if photo.image_url:
        info_lines.append(f"Image URL:\n{photo.image_url}")
    if photo.page_url:
        info_lines.append(f"Page URL:\n{photo.page_url}")

    info = tk.Text(
        right,
        height=20,
        width=36,
        wrap=tk.WORD,
        bg="#020617",
        fg="#e2e8f0",
        relief=tk.FLAT,
        borderwidth=1,
        font=("Consolas", 9),
    )
    info.pack(fill=tk.BOTH, expand=True)
    info.insert(tk.END, "\n\n".join(info_lines))
    info.configure(state=tk.DISABLED)

    buttons = tk.Frame(right, bg="#111827")
    buttons.pack(fill=tk.X, pady=(10, 0))

    if photo.page_url:
        tk.Button(
            buttons,
            text="Open page",
            command=lambda: webbrowser.open(photo.page_url),
            bg="#38bdf8",
            fg="#0f172a",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X, pady=(0, 8))

    if photo.image_url:
        tk.Button(
            buttons,
            text="Open image",
            command=lambda: webbrowser.open(photo.image_url),
            bg="#38bdf8",
            fg="#0f172a",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=tk.X)

    root.bind("<Escape>", lambda _event: root.destroy())
    root.mainloop()

