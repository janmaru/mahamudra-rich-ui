from __future__ import annotations

import math
from typing import Any, Mapping

from rich_ui import SCATTER_SHAPE_VOCABULARY as _SHAPE_TOKENS

try:
    import tkinter as tk
except ImportError:
    tk = None


_AXIS_NAMES = ("X", "Y", "Z")

_DIAMOND_GLYPHS = {"\u25c6", "\u2666", "\u25c7", "\u2b25", "\u2b26"}
_TRI_UP_GLYPHS = {"\u25b2", "\u25b3", "\u25b4", "\u25b5"}
_TRI_DOWN_GLYPHS = {"\u25bc", "\u25bd", "\u25be", "\u25bf"}
_SQUARE_GLYPHS = {"\u25a0", "\u25a1", "\u25aa", "\u25ab", "\u25fc", "\u25fb"}
_CROSS_GLYPHS = {"+", "x", "X", "\u00d7", "\u2715", "\u2716", "*"}
_STAR_GLYPHS = {"\u2605", "\u2606", "\u2726", "\u2727"}
_RINGED_GLYPHS = {"\u2299", "\u229a", "\u25ce"}
_SOLID_CIRCLE_GLYPHS = {"\u25cf", "\u25c9"}
_HOLLOW_CIRCLE_GLYPHS = {"\u25cb", "\u25ef", "\u25cc", "\u25cd", "o", "O"}

_RICH_COLORS: dict[str, str] = {
    "black": "#000000",
    "red": "#cc3030",
    "green": "#30cc30",
    "yellow": "#cccc30",
    "blue": "#3a66ff",
    "magenta": "#cc30cc",
    "cyan": "#30cccc",
    "white": "#cccccc",
    "bright_red": "#ff5555",
    "bright_green": "#55ff55",
    "bright_yellow": "#ffff55",
    "bright_blue": "#5599ff",
    "bright_magenta": "#ff55ff",
    "bright_cyan": "#55ffff",
    "bright_white": "#ffffff",
}


def is_tk_available() -> bool:
    return tk is not None


def _style_to_color(style: Any, default: str = "#cbd5e1") -> str:
    if not isinstance(style, str):
        return default
    for token in style.split():
        color = _RICH_COLORS.get(token.lower())
        if color is not None:
            return color
    return default


def _resolve_shape(shape: Any, glyph: Any) -> str:
    if isinstance(shape, str) and shape in _SHAPE_TOKENS:
        return shape
    text = glyph.strip() if isinstance(glyph, str) else ""
    g = text[0] if text else ""
    if g in _DIAMOND_GLYPHS:
        return "diamond"
    if g in _TRI_UP_GLYPHS:
        return "triangle_up"
    if g in _TRI_DOWN_GLYPHS:
        return "triangle_down"
    if g in _SQUARE_GLYPHS:
        return "square"
    if g in _CROSS_GLYPHS:
        return "cross"
    if g in _STAR_GLYPHS:
        return "star"
    if g in _RINGED_GLYPHS:
        return "ringed"
    if g in _HOLLOW_CIRCLE_GLYPHS:
        return "ring"
    if g in _SOLID_CIRCLE_GLYPHS:
        return "circle"
    return "circle"


def _draw_marker(
    canvas: "tk.Canvas",
    x: float,
    y: float,
    size: float,
    glyph: Any,
    fill: str,
    outline: str = "",
    outline_width: int = 0,
    shape: Any = None,
) -> None:
    edge = outline if outline else fill
    width = outline_width if outline_width else 1
    token = _resolve_shape(shape, glyph)

    if token == "diamond":
        canvas.create_polygon(
            x, y - size, x + size, y, x, y + size, x - size, y,
            fill=fill, outline=edge, width=width,
        )
        return
    if token == "triangle_up":
        canvas.create_polygon(
            x, y - size, x + size, y + size * 0.85, x - size, y + size * 0.85,
            fill=fill, outline=edge, width=width,
        )
        return
    if token == "triangle_down":
        canvas.create_polygon(
            x, y + size, x + size, y - size * 0.85, x - size, y - size * 0.85,
            fill=fill, outline=edge, width=width,
        )
        return
    if token == "square":
        canvas.create_rectangle(
            x - size, y - size, x + size, y + size,
            fill=fill, outline=edge, width=width,
        )
        return
    if token == "cross":
        line_w = max(2, outline_width)
        canvas.create_line(x - size, y - size, x + size, y + size, fill=fill, width=line_w)
        canvas.create_line(x - size, y + size, x + size, y - size, fill=fill, width=line_w)
        return
    if token == "star":
        points: list[float] = []
        for i in range(10):
            r = size if i % 2 == 0 else size * 0.45
            angle = -math.pi / 2 + i * math.pi / 5
            points.extend([x + r * math.cos(angle), y + r * math.sin(angle)])
        canvas.create_polygon(*points, fill=fill, outline=edge, width=width)
        return
    if token == "ringed":
        canvas.create_oval(x - size, y - size, x + size, y + size, fill="", outline=fill, width=2)
        inner = max(2.0, size * 0.35)
        canvas.create_oval(x - inner, y - inner, x + inner, y + inner, fill=fill, outline=fill)
        return
    if token == "ring":
        canvas.create_oval(x - size, y - size, x + size, y + size, fill="", outline=fill, width=2)
        return
    if token == "dot":
        r = max(1.0, size * 0.35)
        canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=fill)
        return
    canvas.create_oval(x - size, y - size, x + size, y + size, fill=fill, outline=edge, width=width)


def _coords(point: Mapping[str, Any], ax1: int, ax2: int) -> tuple[float, float]:
    triple = (float(point["x"]), float(point["y"]), float(point["z"]))
    return triple[ax1], triple[ax2]


def _resolve_axes(points: list[tuple[float, float, float]]) -> tuple[int, int]:
    if not points:
        return 0, 1
    spreads = [
        (axis, max(p[axis] for p in points) - min(p[axis] for p in points))
        for axis in range(3)
    ]
    spreads.sort(key=lambda item: item[1], reverse=True)
    a, b = sorted((spreads[0][0], spreads[1][0]))
    return a, b


def show_scatter_window(payload: Mapping[str, Any], title: str = "Scatter 2D") -> None:
    if tk is None:
        raise RuntimeError("Tkinter is not available in this Python installation.")

    tracks_raw = payload.get("tracks")
    if not isinstance(tracks_raw, list) or not tracks_raw:
        raise RuntimeError("Scatter payload has no tracks.")
    tracks: list[Mapping[str, Any]] = [t for t in tracks_raw if isinstance(t, Mapping)]
    if not tracks:
        raise RuntimeError("Scatter payload tracks are malformed.")

    center_raw = payload.get("center")
    center = center_raw if isinstance(center_raw, Mapping) else None

    root = tk.Tk()
    root.title(f"{title} - Scatter Viewer")
    root.geometry("1100x760")
    root.configure(bg="#0f1117")

    header = tk.Frame(root, bg="#020617", height=44)
    header.pack(side=tk.TOP, fill=tk.X)
    tk.Label(
        header,
        text=title,
        font=("Segoe UI", 14, "bold"),
        bg="#020617",
        fg="#7dd3fc",
    ).pack(pady=10)

    canvas = tk.Canvas(
        root,
        bg="#000000",
        highlightthickness=1,
        highlightbackground="#1e3a4a",
    )
    canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))

    footer = tk.Frame(root, bg="#0f1117")
    footer.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=8)
    legend_label = tk.Label(
        footer,
        text="",
        anchor="w",
        font=("Consolas", 10),
        bg="#0f1117",
        fg="#cbd5e1",
        justify=tk.LEFT,
    )
    legend_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def draw() -> None:
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return

        all_3d: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]
        for track in tracks:
            current = track.get("current")
            if isinstance(current, Mapping):
                all_3d.append((float(current["x"]), float(current["y"]), float(current["z"])))
            for sample in track.get("samples") or []:
                if isinstance(sample, Mapping):
                    all_3d.append((float(sample["x"]), float(sample["y"]), float(sample["z"])))

        ax1, ax2 = _resolve_axes(all_3d)
        plane_label = f"{_AXIS_NAMES[ax1]}-{_AXIS_NAMES[ax2]}"

        projected = [(p[ax1], p[ax2]) for p in all_3d]
        u_min = min(p[0] for p in projected)
        u_max = max(p[0] for p in projected)
        v_min = min(p[1] for p in projected)
        v_max = max(p[1] for p in projected)
        u_range = u_max - u_min if u_max != u_min else 1.0
        v_range = v_max - v_min if v_max != v_min else 1.0

        margin = 60
        usable_w = max(1, width - 2 * margin)
        usable_h = max(1, height - 2 * margin)
        scale = min(usable_w / u_range, usable_h / v_range)
        u_mid = (u_min + u_max) / 2
        v_mid = (v_min + v_max) / 2
        center_x = width / 2
        center_y = height / 2

        def to_px(u: float, v: float) -> tuple[float, float]:
            return center_x + (u - u_mid) * scale, center_y - (v - v_mid) * scale

        for x in range(0, width, 50):
            canvas.create_line(x, 0, x, height, fill="#1a3a3a")
        for y in range(0, height, 50):
            canvas.create_line(0, y, width, y, fill="#1a3a3a")

        sample_count = 0
        for track in tracks:
            track_color = _style_to_color(track.get("style"))
            history_color = _style_to_color(track.get("history_style"), track_color)
            history_shape = track.get("history_shape")
            history_marker = track.get("history_marker")
            samples = [s for s in (track.get("samples") or []) if isinstance(s, Mapping)]
            sample_count += len(samples)
            if len(samples) >= 2:
                for i in range(1, len(samples)):
                    u1, v1 = _coords(samples[i - 1], ax1, ax2)
                    u2, v2 = _coords(samples[i], ax1, ax2)
                    x1, y1 = to_px(u1, v1)
                    x2, y2 = to_px(u2, v2)
                    canvas.create_line(x1, y1, x2, y2, fill=history_color, width=2)
            use_shape = isinstance(history_shape, str) and history_shape in _SHAPE_TOKENS
            for sample in samples:
                u, v = _coords(sample, ax1, ax2)
                x, y = to_px(u, v)
                if use_shape:
                    _draw_marker(canvas, x, y, 3, history_marker, history_color, shape=history_shape)
                else:
                    canvas.create_oval(x - 1, y - 1, x + 1, y + 1, fill=history_color, outline=history_color)

        if center is not None:
            cx_px, cy_px = to_px(0.0, 0.0)
            ccolor = _style_to_color(center.get("style"), "#5599ff")
            _draw_marker(
                canvas, cx_px, cy_px, 8, center.get("marker"), ccolor,
                outline="#7dd3fc", outline_width=2, shape=center.get("shape"),
            )
            clabel = center.get("label")
            if isinstance(clabel, str) and clabel:
                canvas.create_text(cx_px, cy_px - 20, text=clabel, fill=ccolor, font=("Segoe UI", 9, "bold"))

        for track in tracks:
            current = track.get("current")
            if not isinstance(current, Mapping):
                continue
            color = _style_to_color(track.get("style"))
            u, v = _coords(current, ax1, ax2)
            x, y = to_px(u, v)
            _draw_marker(
                canvas, x, y, 7, track.get("marker"), color,
                outline="#ffffff", outline_width=2, shape=track.get("shape"),
            )
            label = track.get("label")
            if isinstance(label, str) and label:
                canvas.create_text(x, y + 20, text=label, fill=color, font=("Segoe UI", 9, "bold"))

        legend_parts: list[str] = [f"Plane {plane_label}"]
        if center is not None:
            cmarker = center.get("marker") or "+"
            clabel = center.get("label")
            if isinstance(clabel, str) and clabel:
                entry = f"{cmarker} {clabel}"
                ccaption = center.get("caption")
                if isinstance(ccaption, str) and ccaption:
                    entry += f" ({ccaption})"
                legend_parts.append(entry)
        for track in tracks:
            label = track.get("label")
            if not isinstance(label, str) or not label:
                continue
            marker = track.get("marker") or "*"
            entry = f"{marker} {label}"
            caption = track.get("caption")
            if isinstance(caption, str) and caption:
                entry += f" ({caption})"
            legend_parts.append(entry)
        legend_parts.append(f"samples: {sample_count}")
        legend_parts.append("ESC to close")
        legend_label.config(text="   |   ".join(legend_parts))

    canvas.bind("<Configure>", lambda _event: draw())
    root.bind("<Escape>", lambda _event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
