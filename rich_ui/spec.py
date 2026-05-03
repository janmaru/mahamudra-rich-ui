from __future__ import annotations

from typing import Any, Mapping

from rich_ui.dto import (
    Action,
    BlockLayout,
    Frame,
    PanelBlock,
    PhotoCardBlock,
    Scatter2DBlock,
    Scatter2DOptions,
    Slot,
    StackBlock,
    StackResponsive,
    TableBlock,
)

_BREAKPOINTS = {"sm", "md", "lg"}
_SCATTER_PLANES = {"auto", "xy", "xz", "yz"}


class SpecError(ValueError):
    """Raised when the input DSL is invalid."""


class DataError(ValueError):
    """Raised at render time when bound data is missing or malformed."""


def parse_spec(spec: Mapping[str, Any]) -> Frame:
    if not isinstance(spec, Mapping):
        raise SpecError("Spec must be a mapping.")

    block_type = spec.get("type")
    if block_type != "frame":
        raise SpecError("Root spec must have type='frame'.")

    title = _optional_text(spec.get("title"), "title")
    raw_slots = spec.get("slots")
    if not isinstance(raw_slots, Mapping) or not raw_slots:
        raise SpecError("Frame must define a non-empty 'slots' mapping.")

    slots = tuple(_parse_slot(slot_name, blocks) for slot_name, blocks in raw_slots.items())
    return Frame(
        title=title,
        slots=slots,
        actions=_parse_actions(spec.get("actions"), "frame"),
    )


def _parse_slot(slot_name: Any, blocks: Any) -> Slot:
    if not isinstance(slot_name, str) or not slot_name.strip():
        raise SpecError("Slot names must be non-empty strings.")
    if not isinstance(blocks, list):
        raise SpecError(f"Slot '{slot_name}' must contain a list of blocks.")

    parsed_blocks = tuple(
        _parse_block(block, path=f"slots.{slot_name}[{index}]")
        for index, block in enumerate(blocks)
    )
    return Slot(name=slot_name, blocks=parsed_blocks)


def _parse_block(block: Any, path: str):
    if not isinstance(block, Mapping):
        raise SpecError(f"{path} must be a mapping.")

    block_type = block.get("type")
    if block_type == "panel":
        return _parse_panel(block, path)
    if block_type == "table":
        return _parse_table(block, path)
    if block_type == "photo_card":
        return _parse_photo_card(block, path)
    if block_type == "scatter_2d":
        return _parse_scatter_2d(block, path)
    if block_type == "stack":
        return _parse_stack(block, path)

    raise SpecError(
        f"{path}.type must be one of: panel, table, photo_card, scatter_2d, stack."
    )


def _parse_panel(block: Mapping[str, Any], path: str) -> PanelBlock:
    title = _optional_text(block.get("title"), f"{path}.title")
    bind = _required_bind(block.get("bind"), path)
    return PanelBlock(
        title=title,
        bind=bind,
        layout=_parse_layout(block.get("layout"), path),
        actions=_parse_actions(block.get("actions"), path),
    )


def _parse_table(block: Mapping[str, Any], path: str) -> TableBlock:
    title = _optional_text(block.get("title"), f"{path}.title")
    bind = _required_bind(block.get("bind"), path)
    return TableBlock(
        title=title,
        bind=bind,
        layout=_parse_layout(block.get("layout"), path),
        actions=_parse_actions(block.get("actions"), path),
    )


def _parse_photo_card(block: Mapping[str, Any], path: str) -> PhotoCardBlock:
    title = _optional_text(block.get("title"), f"{path}.title")
    bind = _required_bind(block.get("bind"), path)

    options = block.get("options")
    if options is not None and not isinstance(options, Mapping):
        raise SpecError(f"{path}.options must be a mapping.")
    mode = _optional_text((options or {}).get("mode"), f"{path}.options.mode") or "native_hint"
    hint = _optional_text((options or {}).get("hint"), f"{path}.options.hint")

    return PhotoCardBlock(
        title=title,
        bind=bind,
        mode=mode,
        hint=hint,
        layout=_parse_layout(block.get("layout"), path),
        actions=_parse_actions(block.get("actions"), path),
    )


def _parse_scatter_2d(block: Mapping[str, Any], path: str) -> Scatter2DBlock:
    title = _optional_text(block.get("title"), f"{path}.title")
    bind = _required_bind(block.get("bind"), path)

    options_raw = block.get("options")
    options: Scatter2DOptions | None = None
    if options_raw is not None:
        if not isinstance(options_raw, Mapping):
            raise SpecError(f"{path}.options must be a mapping.")
        plane = options_raw.get("plane", "auto")
        if not isinstance(plane, str) or plane not in _SCATTER_PLANES:
            raise SpecError(
                f"{path}.options.plane must be one of: auto, xy, xz, yz."
            )
        width = options_raw.get("width")
        if width is not None:
            width = _positive_int(width, f"{path}.options.width")
        height = options_raw.get("height")
        if height is not None:
            height = _positive_int(height, f"{path}.options.height")
        options = Scatter2DOptions(width=width, height=height, plane=plane)

    return Scatter2DBlock(
        title=title,
        bind=bind,
        options=options,
        layout=_parse_layout(block.get("layout"), path),
        actions=_parse_actions(block.get("actions"), path),
    )


def _parse_stack(block: Mapping[str, Any], path: str) -> StackBlock:
    direction = block.get("direction")
    if direction not in {"row", "column"}:
        raise SpecError(f"{path}.direction must be 'row' or 'column'.")

    children = block.get("children")
    if not isinstance(children, list) or not children:
        raise SpecError(f"{path}.children must be a non-empty list.")

    parsed_children = tuple(
        _parse_block(child, path=f"{path}.children[{index}]")
        for index, child in enumerate(children)
    )
    return StackBlock(
        direction=direction,
        children=parsed_children,
        layout=_parse_layout(block.get("layout"), path),
        responsive=_parse_responsive(block.get("responsive"), path),
        actions=_parse_actions(block.get("actions"), path),
    )


def _required_bind(value: Any, path: str) -> str:
    bind = _optional_text(value, f"{path}.bind")
    if bind is None:
        raise SpecError(f"{path}.bind is required.")
    return bind


def _parse_layout(layout: Any, path: str) -> BlockLayout | None:
    if layout is None:
        return None
    if not isinstance(layout, Mapping):
        raise SpecError(f"{path}.layout must be a mapping.")

    spans = None
    raw_span = layout.get("span")
    if raw_span is not None:
        if not isinstance(raw_span, Mapping) or not raw_span:
            raise SpecError(f"{path}.layout.span must be a non-empty mapping.")
        spans = {}
        for key, value in raw_span.items():
            if key not in _BREAKPOINTS:
                raise SpecError(f"{path}.layout.span keys must be one of: sm, md, lg.")
            if isinstance(value, bool) or not isinstance(value, int):
                raise SpecError(f"{path}.layout.span.{key} must be an integer.")
            if value < 1 or value > 12:
                raise SpecError(f"{path}.layout.span.{key} must be between 1 and 12.")
            spans[key] = value

    min_width = None
    if layout.get("min_width") is not None:
        min_width = _positive_int(layout.get("min_width"), f"{path}.layout.min_width")

    equal_height = None
    if layout.get("equal_height") is not None:
        equal_height = _bool_value(layout.get("equal_height"), f"{path}.layout.equal_height")

    pin_footer = None
    if layout.get("pin_footer") is not None:
        pin_footer = _bool_value(layout.get("pin_footer"), f"{path}.layout.pin_footer")

    return BlockLayout(
        spans=spans or None,
        min_width=min_width,
        equal_height=equal_height,
        pin_footer=pin_footer,
    )


def _parse_responsive(responsive: Any, path: str) -> StackResponsive | None:
    if responsive is None:
        return None
    if not isinstance(responsive, Mapping) or not responsive:
        raise SpecError(f"{path}.responsive must be a non-empty mapping.")

    directions: dict[str, str] = {}
    for key, value in responsive.items():
        if key not in _BREAKPOINTS:
            raise SpecError(f"{path}.responsive keys must be one of: sm, md, lg.")
        if value not in {"row", "column"}:
            raise SpecError(f"{path}.responsive.{key} must be 'row' or 'column'.")
        directions[key] = value
    return StackResponsive(directions=directions)


def _parse_actions(actions: Any, path: str) -> tuple[Action, ...]:
    if actions is None:
        return ()
    if not isinstance(actions, list) or not actions:
        raise SpecError(f"{path}.actions must be a non-empty list.")

    parsed_actions: list[Action] = []
    seen_ids: set[str] = set()
    for index, action in enumerate(actions):
        action_path = f"{path}.actions[{index}]"
        if not isinstance(action, Mapping):
            raise SpecError(f"{action_path} must be a mapping.")
        action_id = _required_text(action.get("id"), f"{action_path}.id")
        if action_id in seen_ids:
            raise SpecError(f"{action_path}.id must be unique within the block.")
        seen_ids.add(action_id)
        label = _optional_text(action.get("label"), f"{action_path}.label")
        key = _optional_text(action.get("key"), f"{action_path}.key")
        if key is not None:
            if len(key) != 1:
                raise SpecError(f"{action_path}.key must be a single character.")
            key = key.upper()
        parsed_actions.append(Action(id=action_id, label=label, key=key))
    return tuple(parsed_actions)


def _optional_text(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SpecError(f"{path} must be a string when provided.")
    stripped = value.strip()
    return stripped or None


def _required_text(value: Any, path: str) -> str:
    text = _optional_text(value, path)
    if text is None:
        raise SpecError(f"{path} is required.")
    return text


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpecError(f"{path} must be an integer.")
    if value < 1:
        raise SpecError(f"{path} must be >= 1.")
    return value


def _bool_value(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SpecError(f"{path} must be a boolean.")
    return value
