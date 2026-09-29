from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
from typing import Any, Mapping

from rich.console import Console

from examples.common.photo_models import PhotoResource
from examples.common.photo_openers import open_photo_with_best_available
from examples.voyager.adapter import DEFAULT_CACHE_DIR, build_voyager_from_cache
from rich_ui.dto import Action, Block, Frame, PanelBlock, PhotoCardBlock, Slot, StackBlock, TableBlock
from rich_ui import Theme, ViewMode, find_data_issues, render
from rich_ui.spec import parse_spec


def build_demo_payload() -> tuple[dict, dict, dict]:
    spec = {
        "type": "frame",
        "title": "Voyager Demo",
        "slots": {
            "header": [
                {"type": "panel", "title": "Mission", "bind": "mission"}
            ],
            "body": [
                {
                    "type": "stack",
                    "direction": "row",
                    "children": [
                        {"type": "table", "title": "Spacecraft", "bind": "spacecraft"},
                        {"type": "panel", "title": "Status", "bind": "status"},
                    ],
                }
            ],
            "bottom": [
                {"type": "panel", "title": "Update", "bind": "update"}
            ],
        },
    }
    data = {
        "mission": [
            "Voyager 1 - 167 AU - 17 km/s",
            "Voyager 2 - 138 AU - 15 km/s",
        ],
        "spacecraft": [
            {"Name": "Voyager 1", "Distance": "167 AU", "Speed": "17 km/s"},
            {"Name": "Voyager 2", "Distance": "138 AU", "Speed": "15 km/s"},
        ],
        "status": ["DSN: OK", "Weather: Quiet", "Alerts: None"],
        "update": [
            "Last refresh: 2026-04-29 10:30 UTC",
            "Source: cached snapshot",
        ],
    }
    sync: dict = {}
    return spec, data, sync


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a demo rich-ui frame.")
    parser.add_argument(
        "--example",
        choices=["voyager"],
        help="Render a built-in integration example instead of a local mock spec.",
    )
    parser.add_argument(
        "--view",
        choices=[mode.value for mode in ViewMode],
        default=ViewMode.DASHBOARD.value,
        help="Rendering mode",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        help="Path to a JSON spec file.",
    )
    parser.add_argument(
        "--data",
        type=Path,
        help="Path to a JSON file with the data payload bound to the spec.",
    )
    parser.add_argument(
        "--sync",
        type=Path,
        help="Path to a JSON file with the per-bind sync metadata.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Cache directory used by --example voyager.",
    )
    parser.add_argument(
        "--open-photo",
        action="store_true",
        help="Open the current photo for supported examples.",
    )
    parser.add_argument(
        "--open-scatter",
        action="store_true",
        help="Open the current scatter_2d block in a dedicated viewer window.",
    )
    parser.add_argument(
        "--action",
        help="Execute a DSL action by id for supported examples.",
    )
    return parser.parse_args()


def load_payload(args: argparse.Namespace) -> tuple[dict, dict, dict]:
    if args.example == "voyager":
        spec, data, sync = build_voyager_from_cache(args.cache_dir)
    elif args.spec is not None:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        data = _load_sibling(args.spec, "data")
        sync = _load_sibling(args.spec, "sync")
    else:
        spec, data, sync = build_demo_payload()
    if args.data is not None:
        data = json.loads(args.data.read_text(encoding="utf-8"))
    if args.sync is not None:
        sync = json.loads(args.sync.read_text(encoding="utf-8"))
    return spec, data, sync


def _load_sibling(spec_path: Path, suffix: str) -> dict:
    sibling = spec_path.with_name(f"{spec_path.stem}.{suffix}.json")
    if sibling.exists():
        return json.loads(sibling.read_text(encoding="utf-8"))
    return {}


def collect_action_ids(frame: Frame) -> set[str]:
    return {action.id for action in iter_actions(frame)}


def collect_key_actions(frame: Frame) -> dict[str, Action]:
    bindings: dict[str, Action] = {}
    for action in iter_actions(frame):
        if action.key is None:
            continue
        key = action.key.upper()
        existing = bindings.get(key)
        if existing is not None and existing.id != action.id:
            raise SystemExit(f"Action key '{key}' is assigned to multiple actions.")
        bindings[key] = action
    return bindings


def iter_actions(frame: Frame) -> tuple[Action, ...]:
    actions: list[Action] = list(frame.actions)
    for slot in frame.slots:
        actions.extend(_iter_slot_actions(slot))
    return tuple(actions)


def _iter_slot_actions(slot: Slot) -> list[Action]:
    actions: list[Action] = []
    for block in slot.blocks:
        actions.extend(_iter_block_actions(block))
    return actions


def _iter_block_actions(block: Block) -> list[Action]:
    actions = list(getattr(block, "actions", ()))
    if isinstance(block, StackBlock):
        for child in block.children:
            actions.extend(_iter_block_actions(child))
    return actions


def find_photo_resource_for_action(
    node: object,
    action_id: str,
    cache_dir: Path,
    example: str | None,
    data: Mapping[str, Any] | None = None,
) -> PhotoResource | None:
    if isinstance(node, dict):
        if node.get("type") == "photo_card":
            actions = node.get("actions")
            photo = _resolve_photo_payload(node, data)
            if isinstance(actions, list) and isinstance(photo, dict):
                for action in actions:
                    if isinstance(action, dict) and action.get("id") == action_id:
                        return _photo_resource_from_payload(photo, example, cache_dir)
            if action_id == "open_photo" and isinstance(photo, dict):
                return _photo_resource_from_payload(photo, example, cache_dir)
        for value in node.values():
            resource = find_photo_resource_for_action(value, action_id, cache_dir, example, data)
            if resource is not None:
                return resource
        return None
    if isinstance(node, list):
        for item in node:
            resource = find_photo_resource_for_action(item, action_id, cache_dir, example, data)
            if resource is not None:
                return resource
    return None


def _resolve_photo_payload(
    photo_card: Mapping[str, Any],
    data: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    bind = photo_card.get("bind")
    if isinstance(bind, str) and bind.strip():
        if not data:
            return None
        candidate = data.get(bind)
        return candidate if isinstance(candidate, Mapping) else None
    photo = photo_card.get("photo")
    return photo if isinstance(photo, Mapping) else None


def _photo_resource_from_payload(
    photo: Mapping[str, Any],
    example: str | None,
    cache_dir: Path,
) -> PhotoResource:
    local_path = None
    if example == "voyager":
        candidate = cache_dir / "photo.bin"
        local_path = candidate if candidate.exists() else None
    return PhotoResource(
        title=str(photo.get("title") or "Untitled photo"),
        published=_optional_string(photo.get("published")),
        page_url=_optional_string(photo.get("url")),
        image_url=_optional_string(photo.get("image_url")),
        local_path=local_path,
    )


def _optional_string(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _can_open_photo(spec: dict, example: str | None, cache_dir: Path, data: Mapping[str, Any] | None) -> tuple[bool, str | None]:
    photo = find_photo_resource_for_action(spec, "open_photo", cache_dir, example, data)
    if photo is None:
        return False, "no photo resource is available"
    if photo.local_path is None and not photo.page_url and not photo.image_url:
        return False, "the photo action has no local file or URL target"
    return True, None


def find_scatter_payload_for_action(
    spec: dict,
    action_id: str,
    data: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], str | None] | None:
    block = _find_scatter_block(spec, action_id)
    if block is None:
        return None
    bind = block.get("bind")
    if not isinstance(bind, str) or not data:
        return None
    payload = data.get(bind)
    if not isinstance(payload, Mapping):
        return None
    title = block.get("title") if isinstance(block.get("title"), str) else None
    return payload, title


def _find_scatter_block(node: object, action_id: str) -> Mapping[str, Any] | None:
    if isinstance(node, dict):
        if node.get("type") == "scatter_2d":
            actions = node.get("actions")
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict) and action.get("id") == action_id:
                        return node
        for value in node.values():
            found = _find_scatter_block(value, action_id)
            if found is not None:
                return found
        return None
    if isinstance(node, list):
        for item in node:
            found = _find_scatter_block(item, action_id)
            if found is not None:
                return found
    return None


def _can_open_scatter(spec: dict, data: Mapping[str, Any] | None) -> tuple[bool, str | None]:
    try:
        from examples.common.tk_scatter_viewer import is_tk_available
    except ImportError:
        return False, "tkinter is not available"
    if not is_tk_available():
        return False, "tkinter is not available"
    found = find_scatter_payload_for_action(spec, "open_scatter", data)
    if found is None:
        return False, "no scatter_2d data is available"
    payload, _ = found
    tracks = payload.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        return False, "scatter has no tracks"
    return True, None


def resolve_action_statuses(
    spec: dict,
    frame: Frame,
    example: str | None,
    cache_dir: Path,
    data: Mapping[str, Any] | None,
) -> dict[str, tuple[bool, str | None]]:
    statuses: dict[str, tuple[bool, str | None]] = {}
    for action_id in collect_action_ids(frame):
        if action_id == "open_photo":
            statuses[action_id] = _can_open_photo(spec, example, cache_dir, data)
            continue
        if action_id == "open_scatter":
            statuses[action_id] = _can_open_scatter(spec, data)
            continue
        statuses[action_id] = (False, "no runtime handler is registered")
    return statuses


def apply_action_statuses(frame: Frame, statuses: dict[str, tuple[bool, str | None]]) -> Frame:
    return replace(
        frame,
        actions=_resolve_actions(frame.actions, statuses),
        slots=tuple(_apply_slot_action_statuses(slot, statuses) for slot in frame.slots),
    )


def _apply_slot_action_statuses(slot: Slot, statuses: dict[str, tuple[bool, str | None]]) -> Slot:
    return replace(slot, blocks=tuple(_apply_block_action_statuses(block, statuses) for block in slot.blocks))


def _apply_block_action_statuses(block: Block, statuses: dict[str, tuple[bool, str | None]]) -> Block:
    if isinstance(block, StackBlock):
        return replace(
            block,
            actions=_resolve_actions(block.actions, statuses),
            children=tuple(_apply_block_action_statuses(child, statuses) for child in block.children),
        )
    return replace(block, actions=_resolve_actions(block.actions, statuses))


def _resolve_actions(actions: tuple[Action, ...], statuses: dict[str, tuple[bool, str | None]]) -> tuple[Action, ...]:
    resolved_actions: list[Action] = []
    for action in actions:
        available, reason = statuses.get(action.id, (False, "no runtime handler is registered"))
        resolved_actions.append(replace(action, available=available, unavailable_reason=reason))
    return tuple(resolved_actions)


def warn_unavailable_actions(console: Console, frame: Frame) -> None:
    warnings: dict[str, str | None] = {}
    for action in iter_actions(frame):
        if action.available:
            continue
        warnings.setdefault(action.id, action.unavailable_reason)
    for action_id, reason in warnings.items():
        suffix = f": {reason}" if reason else ""
        console.print(f"[yellow]Warning:[/yellow] action '{action_id}' is unavailable{suffix}.")


def execute_action(
    action_id: str,
    spec: dict,
    example: str | None,
    cache_dir: Path,
    data: Mapping[str, Any] | None,
) -> None:
    if action_id == "open_photo":
        photo = find_photo_resource_for_action(spec, action_id, cache_dir, example, data)
        if photo is None:
            raise SystemExit(
                "Action 'open_photo' requires a photo_card with a page or image URL."
            )
        open_photo_with_best_available(photo)
        return
    if action_id == "open_scatter":
        from examples.common.tk_scatter_viewer import show_scatter_window

        found = find_scatter_payload_for_action(spec, action_id, data)
        if found is None:
            raise SystemExit(
                "Action 'open_scatter' requires a scatter_2d block with valid data."
            )
        payload, title = found
        show_scatter_window(payload, title=title or "Scatter 2D")
        return
    raise SystemExit(f"Action '{action_id}' is declared but no runtime handler is registered.")


def _read_action_key() -> str:
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getwch()
        if key in {"\r", "\n"}:
            return ""
        return key.upper()
    return input().strip().upper()[:1]


def maybe_handle_key_actions(
    console: Console,
    frame: Frame,
    spec: dict,
    example: str | None,
    cache_dir: Path,
    data: Mapping[str, Any] | None,
) -> None:
    bindings = collect_key_actions(frame)
    if not bindings:
        return
    pressed = _read_action_key()
    if not pressed:
        return
    action = bindings.get(pressed.upper())
    if action is None:
        return
    if not action.available:
        reason = f": {action.unavailable_reason}" if action.unavailable_reason else ""
        console.print(f"[yellow]Action '{action.id}' is unavailable{reason}.[/yellow]")
        return
    execute_action(action.id, spec, example, cache_dir, data)


def warn_data_issues(console: Console, frame: Frame, data: dict) -> None:
    for issue in find_data_issues(frame, data):
        console.print(f"[yellow]Warning:[/yellow] {issue.message}.")


def main() -> None:
    args = parse_args()
    spec, data, sync = load_payload(args)
    parsed_frame = parse_spec(spec)
    action_statuses = resolve_action_statuses(spec, parsed_frame, args.example, args.cache_dir, data)
    resolved_frame = apply_action_statuses(parsed_frame, action_statuses)
    direct_flags = sum(1 for flag in (args.open_photo, args.open_scatter, bool(args.action)) if flag)
    if direct_flags > 1:
        raise SystemExit("Use only one of --action, --open-photo, --open-scatter.")
    action_id = args.action
    if action_id is None and args.open_photo:
        action_id = "open_photo"
    if action_id is None and args.open_scatter:
        action_id = "open_scatter"
    if action_id is not None:
        declared_actions = collect_action_ids(resolved_frame)
        if action_id not in declared_actions:
            raise SystemExit(f"Action '{action_id}' is not declared in the loaded spec.")
        is_available, reason = action_statuses.get(action_id, (False, "no runtime handler is registered"))
        if not is_available:
            suffix = f": {reason}" if reason else ""
            raise SystemExit(f"Action '{action_id}' is unavailable{suffix}.")
        execute_action(action_id, spec, args.example, args.cache_dir, data)
        return
    console = Console()
    warn_unavailable_actions(console, resolved_frame)
    warn_data_issues(console, resolved_frame, data)
    console.print(render(resolved_frame, data=data, sync=sync, view=ViewMode(args.view), theme=Theme()))
    maybe_handle_key_actions(console, resolved_frame, spec, args.example, args.cache_dir, data)


if __name__ == "__main__":
    main()

