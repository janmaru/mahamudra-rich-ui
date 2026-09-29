from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from examples.common.photo_openers import open_photo_with_best_available
from examples.voyager.adapter import (
    DEFAULT_CACHE_DIR,
    build_voyager_from_cache,
    build_voyager_photo_resource,
)
from rich_ui import Theme, ViewMode, find_data_issues, parse_spec, render


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render rich-ui using real Voyager Explorer cache data."
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Path to the Voyager-Explorer cache directory.",
    )
    parser.add_argument(
        "--view",
        choices=[mode.value for mode in ViewMode],
        default=ViewMode.DASHBOARD.value,
        help="Rendering mode",
    )
    parser.add_argument(
        "--open-photo",
        action="store_true",
        help="Open the current Voyager photo with the best available opener.",
    )
    parser.add_argument(
        "--open-scatter",
        action="store_true",
        help="Open the trajectory scatter_2d in a dedicated viewer window.",
    )
    parser.add_argument(
        "--action",
        help="Execute a Voyager example action by id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    direct_flags = sum(1 for flag in (args.open_photo, args.open_scatter, bool(args.action)) if flag)
    if direct_flags > 1:
        raise SystemExit("Use only one of --action, --open-photo, --open-scatter.")
    action_id = args.action
    if action_id is None and args.open_photo:
        action_id = "open_photo"
    if action_id is None and args.open_scatter:
        action_id = "open_scatter"
    if action_id == "open_photo":
        photo = build_voyager_photo_resource(args.cache_dir)
        if photo is None:
            raise SystemExit("No Voyager photo cache is available.")
        open_photo_with_best_available(photo)
        return
    if action_id == "open_scatter":
        from examples.common.tk_scatter_viewer import show_scatter_window

        _, data, _ = build_voyager_from_cache(args.cache_dir)
        payload = data.get("trajectory")
        if not isinstance(payload, dict) or not payload.get("tracks"):
            raise SystemExit("Trajectory data is not available for the scatter viewer.")
        show_scatter_window(payload, title="Voyager Trajectory")
        return
    if action_id is not None:
        raise SystemExit(f"Action '{action_id}' is not supported by the Voyager example.")
    spec, data, sync = build_voyager_from_cache(args.cache_dir)
    frame = parse_spec(spec)
    console = Console()
    for issue in find_data_issues(frame, data):
        console.print(f"[yellow]Warning:[/yellow] {issue.message}.")
    console.print(render(frame, data=data, sync=sync, view=ViewMode(args.view), theme=Theme()))


if __name__ == "__main__":
    main()
