from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from rich import box
from rich.columns import Columns
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

from rich_ui.dto import (
    Action,
    Block,
    BlockLayout,
    BlockMeta,
    Frame,
    PanelBlock,
    PanelItem,
    PhotoCardBlock,
    Scatter2DBlock,
    Scatter2DOptions,
    Slot,
    StackBlock,
    TableBlock,
    TextSegment,
)
from rich_ui.spec import parse_spec
from rich_ui.theme import Theme
from rich_ui.view_mode import ViewMode

_DEFAULT_SCATTER_WIDTH = 60
_DEFAULT_SCATTER_HEIGHT = 16
_MIN_SCATTER_WIDTH = 24

SCATTER_SHAPE_VOCABULARY: frozenset[str] = frozenset({
    "circle",
    "ring",
    "ringed",
    "diamond",
    "triangle_up",
    "triangle_down",
    "square",
    "cross",
    "star",
    "dot",
})
_MIN_SCATTER_HEIGHT = 6


@dataclass(frozen=True)
class DataIssue:
    bind: str
    kind: str
    message: str


@dataclass(frozen=True)
class _RenderContext:
    data: Mapping[str, Any]
    sync: Mapping[str, Any]


_BREAKPOINT_ORDER = {
    "sm": ("sm", "md", "lg"),
    "md": ("md", "lg", "sm"),
    "lg": ("lg", "md", "sm"),
}


def render(
    spec: Mapping[str, Any] | Frame,
    data: Mapping[str, Any] | None = None,
    sync: Mapping[str, Any] | None = None,
    view: ViewMode | str = ViewMode.DASHBOARD,
    theme: Theme | None = None,
) -> RenderableType:
    frame = spec if isinstance(spec, Frame) else parse_spec(spec)
    mode = ViewMode(view)
    active_theme = theme or Theme()
    context = _RenderContext(data=data or {}, sync=sync or {})

    if mode is ViewMode.DASHBOARD:
        return _render_dashboard(frame, active_theme, context)
    if mode is ViewMode.PANEL:
        return _render_panel_view(frame, active_theme, context)
    return _render_compact_view(frame, active_theme, context)


def find_data_issues(
    frame: Frame,
    data: Mapping[str, Any] | None,
) -> tuple[DataIssue, ...]:
    bag = data or {}
    issues: list[DataIssue] = []
    for slot in frame.slots:
        for block in slot.blocks:
            issues.extend(_collect_block_issues(block, bag))
    return tuple(issues)


def _collect_block_issues(block: Block, data: Mapping[str, Any]) -> list[DataIssue]:
    issues: list[DataIssue] = []
    if isinstance(block, TableBlock):
        issues.extend(_validate_table_bind(block.bind, data))
    elif isinstance(block, PanelBlock):
        issues.extend(_validate_panel_bind(block.bind, data))
    elif isinstance(block, PhotoCardBlock):
        issues.extend(_validate_photo_card_bind(block.bind, data))
    elif isinstance(block, Scatter2DBlock):
        issues.extend(_validate_scatter_2d_bind(block.bind, data))
    elif isinstance(block, StackBlock):
        for child in block.children:
            issues.extend(_collect_block_issues(child, data))
    return issues


def _validate_table_bind(bind: str, data: Mapping[str, Any]) -> list[DataIssue]:
    if bind not in data:
        return [DataIssue(bind=bind, kind="missing", message=f"bind '{bind}' is missing in data payload")]
    payload = data[bind]
    if not isinstance(payload, list):
        return [DataIssue(bind=bind, kind="invalid_shape", message=f"bind '{bind}' must be a list of records")]
    if not payload:
        return [DataIssue(bind=bind, kind="empty", message=f"bind '{bind}' has no records")]
    first = payload[0]
    if not isinstance(first, Mapping):
        return [DataIssue(bind=bind, kind="invalid_record", message=f"bind '{bind}' records must be objects")]
    expected_keys = tuple(str(key) for key in first.keys())
    for index, record in enumerate(payload[1:], start=1):
        if not isinstance(record, Mapping):
            return [DataIssue(bind=bind, kind="invalid_record", message=f"bind '{bind}' record [{index}] is not an object")]
        actual_keys = tuple(str(key) for key in record.keys())
        if actual_keys != expected_keys:
            return [
                DataIssue(
                    bind=bind,
                    kind="inconsistent_keys",
                    message=f"bind '{bind}' record [{index}] keys differ from the first record",
                )
            ]
    return []


def _validate_panel_bind(bind: str, data: Mapping[str, Any]) -> list[DataIssue]:
    if bind not in data:
        return [DataIssue(bind=bind, kind="missing", message=f"bind '{bind}' is missing in data payload")]
    payload = data[bind]
    if not isinstance(payload, list):
        return [DataIssue(bind=bind, kind="invalid_shape", message=f"bind '{bind}' must be a list of items")]
    for index, item in enumerate(payload):
        if isinstance(item, str):
            continue
        if isinstance(item, Mapping) and ("text" in item or "segments" in item):
            continue
        return [
            DataIssue(
                bind=bind,
                kind="invalid_record",
                message=f"bind '{bind}' item [{index}] must be a string or an object with 'text'/'segments'",
            )
        ]
    return []


def _validate_scatter_2d_bind(bind: str, data: Mapping[str, Any]) -> list[DataIssue]:
    if bind not in data:
        return [DataIssue(bind=bind, kind="missing", message=f"bind '{bind}' is missing in data payload")]
    payload = data[bind]
    if not isinstance(payload, Mapping):
        return [DataIssue(bind=bind, kind="invalid_shape", message=f"bind '{bind}' must be an object")]

    center = payload.get("center")
    if center is not None:
        if not isinstance(center, Mapping):
            return [DataIssue(bind=bind, kind="invalid_field", message=f"bind '{bind}' field 'center' must be an object")]
        for field in ("label", "caption", "marker", "style", "shape"):
            value = center.get(field)
            if value is not None and not isinstance(value, str):
                return [DataIssue(
                    bind=bind, kind="invalid_field",
                    message=f"bind '{bind}' field 'center.{field}' must be a string when provided",
                )]
        center_shape = center.get("shape")
        if isinstance(center_shape, str) and center_shape not in SCATTER_SHAPE_VOCABULARY:
            return [DataIssue(
                bind=bind, kind="invalid_field",
                message=f"bind '{bind}' field 'center.shape' must be one of {sorted(SCATTER_SHAPE_VOCABULARY)}",
            )]

    tracks = payload.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        return [DataIssue(bind=bind, kind="missing_tracks", message=f"bind '{bind}' must define a non-empty 'tracks' list")]

    for index, track in enumerate(tracks):
        if not isinstance(track, Mapping):
            return [DataIssue(
                bind=bind, kind="invalid_record",
                message=f"bind '{bind}' track [{index}] must be an object",
            )]
        for field in ("label", "caption", "marker", "style", "history_marker", "history_style", "shape", "history_shape"):
            value = track.get(field)
            if value is not None and not isinstance(value, str):
                return [DataIssue(
                    bind=bind, kind="invalid_field",
                    message=f"bind '{bind}' track [{index}].{field} must be a string when provided",
                )]
        for shape_field in ("shape", "history_shape"):
            shape_value = track.get(shape_field)
            if isinstance(shape_value, str) and shape_value not in SCATTER_SHAPE_VOCABULARY:
                return [DataIssue(
                    bind=bind, kind="invalid_field",
                    message=f"bind '{bind}' track [{index}].{shape_field} must be one of {sorted(SCATTER_SHAPE_VOCABULARY)}",
                )]
        samples = track.get("samples")
        if samples is not None:
            if not isinstance(samples, list):
                return [DataIssue(
                    bind=bind, kind="invalid_record",
                    message=f"bind '{bind}' track [{index}].samples must be a list",
                )]
            for s_idx, sample in enumerate(samples):
                if not _is_scatter_point(sample):
                    return [DataIssue(
                        bind=bind, kind="invalid_record",
                        message=f"bind '{bind}' track [{index}].samples[{s_idx}] must have numeric x, y, z",
                    )]
        current = track.get("current")
        if current is not None and not _is_scatter_point(current):
            return [DataIssue(
                bind=bind, kind="invalid_record",
                message=f"bind '{bind}' track [{index}].current must have numeric x, y, z",
            )]
        if current is None and not samples:
            return [DataIssue(
                bind=bind, kind="invalid_record",
                message=f"bind '{bind}' track [{index}] must define 'current' or non-empty 'samples'",
            )]
    return []


def _is_scatter_point(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    for axis in ("x", "y", "z"):
        coord = value.get(axis)
        if isinstance(coord, bool) or not isinstance(coord, (int, float)):
            return False
    return True


def _validate_photo_card_bind(bind: str, data: Mapping[str, Any]) -> list[DataIssue]:
    if bind not in data:
        return [DataIssue(bind=bind, kind="missing", message=f"bind '{bind}' is missing in data payload")]
    payload = data[bind]
    if not isinstance(payload, Mapping):
        return [DataIssue(bind=bind, kind="invalid_shape", message=f"bind '{bind}' must be an object")]
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        return [DataIssue(bind=bind, kind="missing_title", message=f"bind '{bind}' must include a non-empty 'title'")]
    for field in ("published", "url", "image_url"):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            return [
                DataIssue(
                    bind=bind,
                    kind="invalid_field",
                    message=f"bind '{bind}' field '{field}' must be a string when provided",
                )
            ]
    return []


def _render_dashboard(frame: Frame, theme: Theme, context: _RenderContext) -> RenderableType:
    if not frame.slots:
        return Panel(Text("Empty frame", style=theme.muted_style), border_style=theme.frame_border_style)

    sections = [_compose_slot(slot, theme, ViewMode.DASHBOARD, context) for slot in frame.slots]
    return Panel(
        Group(*sections),
        title=_title_text(frame.title, theme),
        border_style=theme.frame_border_style,
    )


def _render_panel_view(frame: Frame, theme: Theme, context: _RenderContext) -> RenderableType:
    blocks: list[RenderableType] = []
    if frame.title:
        blocks.append(
            Panel(
                Text(frame.title, style=theme.title_style),
                border_style=theme.frame_border_style,
            )
        )

    for slot in frame.slots:
        blocks.append(
            Panel(
                _compose_slot(slot, theme, ViewMode.PANEL, context),
                title=Text(slot.name.upper(), style=theme.slot_title_style),
                border_style=theme.slot_border_style,
            )
        )

    return Group(*blocks)


def _render_compact_view(frame: Frame, theme: Theme, context: _RenderContext) -> RenderableType:
    blocks: list[RenderableType] = []
    if frame.title:
        blocks.append(Text(frame.title, style=theme.title_style))

    for slot in frame.slots:
        blocks.append(Text(slot.name.upper(), style=theme.slot_title_style))
        blocks.append(_compose_slot(slot, theme, ViewMode.COMPACT, context))

    return Group(*blocks)


def _compose_slot(slot: Slot, theme: Theme, view: ViewMode, context: _RenderContext) -> RenderableType:
    renderables = [_render_block(block, theme, view, context) for block in slot.blocks]
    if not renderables:
        return Text("Empty slot", style=theme.muted_style)
    if len(renderables) == 1:
        return renderables[0]
    return Group(*renderables)


def _render_block(
    block: Block,
    theme: Theme,
    view: ViewMode,
    context: _RenderContext,
    target_height: int | None = None,
    target_width: int | None = None,
) -> RenderableType:
    if isinstance(block, PanelBlock):
        return _render_panel_block(block, theme, context, target_height, target_width)
    if isinstance(block, TableBlock):
        return _render_table_block(block, theme, view, context, target_height, target_width)
    if isinstance(block, PhotoCardBlock):
        return _render_photo_card_block(block, theme, context, target_height, target_width)
    if isinstance(block, Scatter2DBlock):
        return _render_scatter_2d_block(block, theme, context, target_height, target_width)
    if isinstance(block, StackBlock):
        return _render_stack_block(block, theme, view, context)
    raise TypeError(f"Unsupported block: {type(block)!r}")


def _render_stack_block(block: StackBlock, theme: Theme, view: ViewMode, context: _RenderContext) -> RenderableType:
    children = [_render_block(child, theme, view, context) for child in block.children]
    direction = _stack_direction(block)

    stack_body: RenderableType
    if view is ViewMode.COMPACT or direction == "column":
        stack_body = Group(*children)
    elif not _has_responsive_rules(block):
        stack_body = Columns(children, expand=True, equal=True)
    else:
        stack_body = _render_responsive_rows(block, theme, view, context)
    action_line = _action_renderable(block.actions, theme)
    if action_line is None:
        return stack_body
    return Group(stack_body, Rule(style=theme.muted_style), action_line)


def _render_panel_block(
    block: PanelBlock,
    theme: Theme,
    context: _RenderContext,
    target_height: int | None = None,
    target_width: int | None = None,
) -> RenderableType:
    issues = _validate_panel_bind(block.bind, context.data)
    if issues:
        return _render_block_placeholder(
            title=block.title,
            border_style=theme.panel_border_style,
            theme=theme,
            actions=block.actions,
            pin_footer=_should_pin_footer(block),
            target_height=target_height,
            target_width=target_width,
            issue=issues[0],
        )

    raw_items = list(context.data[block.bind])
    items = tuple(_panel_item_from_data(raw) for raw in raw_items)
    content = Text()
    for index, item in enumerate(items):
        _append_panel_item(content, item)
        if index < len(items) - 1:
            content.append("\n")

    meta = _meta_from_sync(context.sync.get(block.bind))
    panel_body = _append_auxiliary_lines(
        content,
        meta,
        block.actions,
        theme,
        target_height=target_height,
        target_width=target_width,
        pin_footer=_should_pin_footer(block),
    )
    return Panel(
        panel_body,
        title=_title_text(block.title, theme),
        border_style=theme.panel_border_style,
        height=target_height,
    )


def _render_table_block(
    block: TableBlock,
    theme: Theme,
    view: ViewMode,
    context: _RenderContext,
    target_height: int | None = None,
    target_width: int | None = None,
) -> RenderableType:
    issues = _validate_table_bind(block.bind, context.data)
    if issues:
        return _render_block_placeholder(
            title=block.title,
            border_style=theme.table_border_style,
            theme=theme,
            actions=block.actions,
            pin_footer=_should_pin_footer(block),
            target_height=target_height,
            target_width=target_width,
            issue=issues[0],
        )

    records: list[Mapping[str, Any]] = list(context.data[block.bind])
    columns = tuple(str(key) for key in records[0].keys())

    table = Table(box=box.SIMPLE, expand=True)
    for column in columns:
        table.add_column(column, header_style=theme.table_header_style)
    for record in records:
        table.add_row(*(_stringify_cell(record.get(column)) for column in columns))

    meta = _meta_from_sync(context.sync.get(block.bind))

    if view is ViewMode.COMPACT:
        return _append_auxiliary_lines(table, meta, block.actions, theme)

    panel_body = _append_auxiliary_lines(
        table,
        meta,
        block.actions,
        theme,
        target_height=target_height,
        target_width=target_width,
        pin_footer=_should_pin_footer(block),
    )

    return Panel(
        panel_body,
        title=_title_text(block.title, theme),
        border_style=theme.table_border_style,
        height=target_height,
    )


def _render_photo_card_block(
    block: PhotoCardBlock,
    theme: Theme,
    context: _RenderContext,
    target_height: int | None = None,
    target_width: int | None = None,
) -> RenderableType:
    issues = _validate_photo_card_bind(block.bind, context.data)
    if issues:
        return _render_block_placeholder(
            title=block.title,
            border_style=theme.panel_border_style,
            theme=theme,
            actions=block.actions,
            pin_footer=_should_pin_footer(block),
            target_height=target_height,
            target_width=target_width,
            issue=issues[0],
        )

    payload: Mapping[str, Any] = context.data[block.bind]
    photo_title = str(payload.get("title", ""))
    published = _optional_str(payload.get("published"))
    url = _optional_str(payload.get("url"))
    image_url = _optional_str(payload.get("image_url"))

    lines: list[RenderableType] = [Text(photo_title, style=theme.title_style)]
    if published:
        lines.append(Text(f"Published: {published}"))
    if block.mode == "native_hint":
        lines.append(Text(block.hint or "Open in a native or external viewer", style="italic"))
    elif block.mode == "metadata":
        lines.append(Text("Metadata-only preview", style=theme.muted_style))
    if url:
        lines.append(_link_text("Open page", url, theme))
    if image_url:
        lines.append(_link_text("Open image", image_url, theme))

    photo_body: RenderableType = Group(*lines)
    meta = _meta_from_sync(context.sync.get(block.bind))
    panel_body = _append_auxiliary_lines(
        photo_body,
        meta,
        block.actions,
        theme,
        target_height=target_height,
        target_width=target_width,
        pin_footer=_should_pin_footer(block),
    )
    return Panel(
        panel_body,
        title=_title_text(block.title, theme),
        border_style=theme.panel_border_style,
        height=target_height,
    )


def _render_scatter_2d_block(
    block: Scatter2DBlock,
    theme: Theme,
    context: _RenderContext,
    target_height: int | None = None,
    target_width: int | None = None,
) -> RenderableType:
    issues = _validate_scatter_2d_bind(block.bind, context.data)
    if issues:
        return _render_block_placeholder(
            title=block.title,
            border_style=theme.scatter_border_style,
            theme=theme,
            actions=block.actions,
            pin_footer=_should_pin_footer(block),
            target_height=target_height,
            target_width=target_width,
            issue=issues[0],
        )

    payload: Mapping[str, Any] = context.data[block.bind]
    options = block.options or Scatter2DOptions()

    grid_width = _resolve_scatter_grid_width(options, target_width)
    grid_height = _resolve_scatter_grid_height(options, target_height)

    tracks_data = list(payload["tracks"])
    center_data = payload.get("center") if isinstance(payload.get("center"), Mapping) else None

    all_points: list[tuple[float, float, float]] = []
    for track in tracks_data:
        current = track.get("current")
        if isinstance(current, Mapping):
            all_points.append((float(current["x"]), float(current["y"]), float(current["z"])))
        for sample in track.get("samples") or []:
            if isinstance(sample, Mapping):
                all_points.append((float(sample["x"]), float(sample["y"]), float(sample["z"])))

    ax1_idx, ax2_idx = _resolve_scatter_projection(all_points, options.plane)
    plane_label = f"{['X', 'Y', 'Z'][ax1_idx]}-{['X', 'Y', 'Z'][ax2_idx]}"

    scale_limit = max(
        (math.hypot(p[ax1_idx], p[ax2_idx]) for p in all_points),
        default=1.0,
    ) * 1.15
    if scale_limit < 1:
        scale_limit = 1.0

    grid: list[list[str]] = [[" " for _ in range(grid_width)] for _ in range(grid_height)]
    styles: list[list[str | None]] = [[None for _ in range(grid_width)] for _ in range(grid_height)]
    cx, cy = grid_width // 2, grid_height // 2

    def to_grid(u: float, v: float) -> tuple[int, int]:
        dist = math.hypot(u, v)
        if dist < 1:
            return cx, cy
        angle = math.atan2(v, u)
        compressed = (min(1.0, dist / scale_limit)) ** 0.55
        col = cx + int(compressed * math.cos(angle) * (cx - 3))
        row = cy - int(compressed * math.sin(angle) * (cy - 1))
        return max(0, min(grid_width - 1, col)), max(0, min(grid_height - 1, row))

    if center_data is not None:
        center_marker = _first_glyph(center_data.get("marker")) or "+"
        grid[cy][cx] = center_marker
        styles[cy][cx] = _optional_str(center_data.get("style"))

    for track in tracks_data:
        history_marker = _first_glyph(track.get("history_marker")) or "\u00b7"
        history_style = _optional_str(track.get("history_style"))
        for sample in track.get("samples") or []:
            if not isinstance(sample, Mapping):
                continue
            x, y, z = float(sample["x"]), float(sample["y"]), float(sample["z"])
            u, v = (x, y, z)[ax1_idx], (x, y, z)[ax2_idx]
            col, row = to_grid(u, v)
            if grid[row][col] == " ":
                grid[row][col] = history_marker
                styles[row][col] = history_style

    for track in tracks_data:
        current = track.get("current")
        if not isinstance(current, Mapping):
            continue
        marker = _first_glyph(track.get("marker")) or "*"
        style = _optional_str(track.get("style"))
        x, y, z = float(current["x"]), float(current["y"]), float(current["z"])
        u, v = (x, y, z)[ax1_idx], (x, y, z)[ax2_idx]
        col, row = to_grid(u, v)
        if col == cx and row == cy:
            row = max(0, row - 1)
        grid[row][col] = marker
        styles[row][col] = style

    canvas = Text()
    for r in range(grid_height):
        for c in range(grid_width):
            canvas.append(grid[r][c], style=styles[r][c])
        if r < grid_height - 1:
            canvas.append("\n")

    legend = _build_scatter_legend(plane_label, center_data, tracks_data)
    body = Group(canvas, legend)

    meta = _meta_from_sync(context.sync.get(block.bind))
    panel_body = _append_auxiliary_lines(
        body,
        meta,
        block.actions,
        theme,
        target_height=target_height,
        target_width=target_width,
        pin_footer=_should_pin_footer(block),
    )
    return Panel(
        panel_body,
        title=_title_text(block.title, theme),
        border_style=theme.scatter_border_style,
        height=target_height,
    )


def _resolve_scatter_grid_width(options: Scatter2DOptions, target_width: int | None) -> int:
    if options.width is not None:
        return max(_MIN_SCATTER_WIDTH, options.width)
    if target_width is not None:
        return max(_MIN_SCATTER_WIDTH, min(_DEFAULT_SCATTER_WIDTH, target_width - 4))
    return _DEFAULT_SCATTER_WIDTH


def _resolve_scatter_grid_height(options: Scatter2DOptions, target_height: int | None) -> int:
    if options.height is not None:
        return max(_MIN_SCATTER_HEIGHT, options.height)
    if target_height is not None:
        return max(_MIN_SCATTER_HEIGHT, min(_DEFAULT_SCATTER_HEIGHT, target_height - 5))
    return _DEFAULT_SCATTER_HEIGHT


def _resolve_scatter_projection(
    points: list[tuple[float, float, float]],
    plane: str,
) -> tuple[int, int]:
    if plane == "xy":
        return 0, 1
    if plane == "xz":
        return 0, 2
    if plane == "yz":
        return 1, 2
    if not points:
        return 0, 1
    spreads = [
        (axis, max(p[axis] for p in points) - min(p[axis] for p in points))
        for axis in range(3)
    ]
    spreads.sort(key=lambda item: item[1], reverse=True)
    a, b = sorted((spreads[0][0], spreads[1][0]))
    return a, b


def _build_scatter_legend(
    plane_label: str,
    center: Mapping[str, Any] | None,
    tracks: list[Mapping[str, Any]],
) -> Text:
    legend = Text()
    legend.append(f"Plane {plane_label}", style="bright_green")

    if center is not None:
        marker = _first_glyph(center.get("marker"))
        label = _optional_str(center.get("label"))
        if marker and label:
            style = _optional_str(center.get("style"))
            legend.append("  ")
            legend.append(f"{marker} {label}", style=style)
            caption = _optional_str(center.get("caption"))
            if caption:
                legend.append(f" {caption}", style="dim")

    for track in tracks:
        marker = _first_glyph(track.get("marker"))
        label = _optional_str(track.get("label"))
        if not (marker and label):
            continue
        style = _optional_str(track.get("style"))
        legend.append("  ")
        legend.append(f"{marker} {label}", style=style)
        caption = _optional_str(track.get("caption"))
        if caption:
            legend.append(f" {caption}", style="dim")
    return legend


def _first_glyph(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped[0] if stripped else None


def _render_block_placeholder(
    title: str | None,
    border_style: str,
    theme: Theme,
    actions: tuple[Action, ...],
    pin_footer: bool,
    target_height: int | None,
    target_width: int | None,
    issue: DataIssue,
) -> RenderableType:
    body = Group(
        Text("data unavailable", style=theme.muted_style),
        Text(issue.message, style=theme.action_disabled_style),
    )
    panel_body = _append_auxiliary_lines(
        body,
        None,
        actions,
        theme,
        target_height=target_height,
        target_width=target_width,
        pin_footer=pin_footer,
    )
    return Panel(
        panel_body,
        title=_title_text(title, theme),
        border_style=border_style,
        height=target_height,
    )


def _render_responsive_rows(block: StackBlock, theme: Theme, view: ViewMode, context: _RenderContext) -> RenderableType:
    terminal_width = shutil.get_terminal_size(fallback=(120, 40)).columns
    breakpoint = _current_breakpoint(terminal_width)
    default_span = max(1, 12 // max(1, len(block.children)))
    available_width = max(terminal_width - 6, 24)

    resolved: list[tuple[Block, int]] = []
    for child in block.children:
        span = _resolve_span(child, breakpoint, default_span)
        allocated_width = max(1, int(available_width * span / 12))
        min_width = _resolve_min_width(child)
        if min_width is not None and allocated_width < min_width:
            return Group(*[_render_block(item, theme, view, context) for item in block.children])
        resolved.append((child, span))

    rows: list[list[tuple[Block, int]]] = []
    current_row: list[tuple[Block, int]] = []
    used = 0
    for child, span in resolved:
        if current_row and used + span > 12:
            rows.append(current_row)
            current_row = [(child, span)]
            used = span
            continue
        current_row.append((child, span))
        used += span
    if current_row:
        rows.append(current_row)

    rendered_rows: list[RenderableType] = []
    for row in rows:
        grid = Table.grid(expand=True, padding=(0, 0))
        target_height: int | None = None
        if _should_equalize_row(block):
            measured_heights: list[int] = []
            for child, span in row:
                width = max(1, int(available_width * span / 12))
                renderable = _render_block(child, theme, view, context, target_width=width)
                measured_heights.append(_measure_height(renderable, width))
            target_height = max(measured_heights, default=None)

        row_renderables = []
        for child, span in row:
            width = max(1, int(available_width * span / 12))
            grid.add_column(ratio=span)
            row_renderables.append(
                _render_block(
                    child,
                    theme,
                    view,
                    context,
                    target_height=target_height,
                    target_width=width,
                )
            )
        grid.add_row(*row_renderables)
        rendered_rows.append(grid)
    return Group(*rendered_rows)


def _title_text(title: str | None, theme: Theme) -> Text | None:
    if not title:
        return None
    return Text(title, style=theme.title_style)


def _meta_text(meta: BlockMeta | None, theme: Theme) -> Text | None:
    if meta is None:
        return None

    parts: list[str] = []
    if meta.source:
        parts.append(meta.source)
    if meta.updated_at:
        parts.append(f"updated {_format_age(meta.updated_at)} ago")
    if meta.interval_seconds is not None:
        parts.append(f"every {meta.interval_seconds}s")
    if not parts:
        return None
    return Text(" | ".join(parts), style=theme.muted_style)


def _action_renderable(actions: tuple[Action, ...], theme: Theme) -> RenderableType | None:
    if not actions:
        return None

    lines: list[Text] = []
    for action in actions:
        if action.key and action.label:
            text = f"Press {action.key} to {action.label}"
        elif action.key:
            text = f"Press {action.key} for {action.id}"
        elif action.label:
            text = f"{action.label} [{action.id}]"
        else:
            text = action.id
        if not action.available:
            text = f"{text} (unavailable)"
            lines.append(Text(text, style=theme.action_disabled_style))
        else:
            lines.append(Text(text, style=theme.muted_style))
    return Group(*lines)


def _append_panel_item(content: Text, item: PanelItem) -> None:
    for segment in item.segments:
        _append_text_segment(content, segment)


def _append_text_segment(content: Text, segment: TextSegment) -> None:
    content.append(segment.text, style=segment.style)


def _panel_item_from_data(raw: Any) -> PanelItem:
    if isinstance(raw, str):
        return PanelItem(segments=(TextSegment(text=raw),))
    if isinstance(raw, Mapping):
        segments_raw = raw.get("segments")
        if isinstance(segments_raw, list) and segments_raw:
            segments: list[TextSegment] = []
            for seg in segments_raw:
                if isinstance(seg, Mapping):
                    text = seg.get("text")
                    if isinstance(text, str):
                        style = seg.get("style")
                        segments.append(TextSegment(text=text, style=style if isinstance(style, str) else None))
            if segments:
                return PanelItem(segments=tuple(segments))
        text = raw.get("text")
        if isinstance(text, str):
            style = raw.get("style")
            return PanelItem(segments=(TextSegment(text=text, style=style if isinstance(style, str) else None),))
    return PanelItem(segments=(TextSegment(text=str(raw)),))


def _append_auxiliary_lines(
    body: RenderableType,
    meta: BlockMeta | None,
    actions: tuple[Action, ...],
    theme: Theme,
    target_height: int | None = None,
    target_width: int | None = None,
    pin_footer: bool = False,
) -> RenderableType:
    lines: list[RenderableType] = [body]
    footer: list[RenderableType] = []
    meta_line = _meta_text(meta, theme)
    if meta_line is not None:
        footer.append(meta_line)
    action_line = _action_renderable(actions, theme)
    if action_line is not None:
        footer.append(action_line)
    if footer:
        footer_renderables: list[RenderableType] = [Rule(style=theme.muted_style), *footer]
        if pin_footer and target_height is not None and target_width is not None:
            inner_height = max(1, target_height - 2)
            inner_width = max(1, target_width - 2)
            body_height = _measure_height(body, inner_width)
            footer_height = _measure_height(Group(*footer_renderables), inner_width)
            spacer_lines = max(0, inner_height - body_height - footer_height)
            if spacer_lines:
                lines.extend(Text(" ") for _ in range(spacer_lines))
        lines.extend(footer_renderables)
    if len(lines) == 1:
        return body
    return Group(*lines)


def _stack_direction(block: StackBlock) -> str:
    if block.responsive is None or not block.responsive.directions:
        return block.direction
    breakpoint = _current_breakpoint(shutil.get_terminal_size(fallback=(120, 40)).columns)
    for key in _BREAKPOINT_ORDER[breakpoint]:
        direction = block.responsive.directions.get(key)
        if direction is not None:
            return direction
    return block.direction


def _has_responsive_rules(block: StackBlock) -> bool:
    if block.layout is not None or block.responsive is not None:
        return True
    return any(_get_layout(child) is not None for child in block.children)


def _resolve_span(block: Block, breakpoint: str, default_span: int) -> int:
    layout = _get_layout(block)
    if layout is None or not layout.spans:
        return default_span
    for key in _BREAKPOINT_ORDER[breakpoint]:
        value = layout.spans.get(key)
        if value is not None:
            return value
    return default_span


def _resolve_min_width(block: Block) -> int | None:
    layout = _get_layout(block)
    return None if layout is None else layout.min_width


def _get_layout(block: Block) -> BlockLayout | None:
    return getattr(block, "layout", None)


def _should_equalize_row(block: StackBlock) -> bool:
    layout = block.layout
    return bool(layout is not None and layout.equal_height)


def _should_pin_footer(block: Block) -> bool:
    layout = _get_layout(block)
    if layout is None or layout.pin_footer is None:
        return True
    return layout.pin_footer


def _current_breakpoint(width: int) -> str:
    if width < 100:
        return "sm"
    if width < 160:
        return "md"
    return "lg"


def _link_text(label: str, url: str, theme: Theme) -> Text:
    line = Text()
    line.append(f"{label}: ", style=theme.muted_style)
    line.append(
        url,
        style=Style(
            color="bright_cyan",
            underline=True,
            link=url,
        ),
    )
    return line


def _format_age(updated_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    age_seconds = max(0, int((now - updated_at.astimezone(timezone.utc)).total_seconds()))
    if age_seconds < 60:
        return f"{age_seconds}s"
    minutes, seconds = divmod(age_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _measure_height(renderable: RenderableType, width: int) -> int:
    console = Console(width=max(1, width), force_terminal=True, color_system=None)
    options = console.options.update(width=max(1, width), height=None)
    return len(console.render_lines(renderable, options=options, pad=False))


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _meta_from_sync(payload: Any) -> BlockMeta | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        return None
    source = payload.get("source")
    if source is not None and not isinstance(source, str):
        source = None
    updated_at = _parse_sync_datetime(payload.get("updated_at"))
    interval_seconds = payload.get("interval_seconds")
    if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int):
        interval_seconds = None
    if source is None and updated_at is None and interval_seconds is None:
        return None
    return BlockMeta(source=source, updated_at=updated_at, interval_seconds=interval_seconds)


def _parse_sync_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
