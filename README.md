# rich-ui

A small Python library that turns a JSON-friendly UI DSL into `rich` renderables.

The project is intentionally focused on presentation:

- no domain logic
- no network calls
- no JSON fetching pipeline
- no app framework

It accepts three independent inputs — a structural **spec**, a **data** payload, and an optional **sync** map — validates them, converts them into internal DTOs, and renders them with `rich`.

## The three planes

`rich-ui` separates UI rendering into three independent inputs:

| Plane | What it contains | Where it comes from |
|---|---|---|
| **spec** | Structure: frame, slots, blocks, `bind` keys, `layout`, `actions` | Hand-written, static (e.g. `mocks/voyager.json`) |
| **data** | The values bound to each `bind` key | An API/service or a static JSON file |
| **sync** | Per-bind freshness metadata (`source`, `updated_at`, `interval_seconds`) | The orchestrator/cron that schedules the data fetch — the API itself does not know it |

The spec never carries values. The data never carries layout. The sync never carries content.

## Quick start

Requires Python 3.10+.

### Windows PowerShell

```powershell
Set-Location C:\Coding\rich-ui
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\main.py --spec .\mocks\voyager.json --view dashboard
```

`main.py` auto-discovers sibling files: when `--spec mocks/voyager.json` is passed, it also loads `mocks/voyager.data.json` and `mocks/voyager.sync.json` if present. Both can be overridden explicitly:

```powershell
python .\main.py --spec .\mocks\voyager.json --data .\path\to\custom.data.json --sync .\path\to\custom.sync.json
```

For examples that use the native photo viewer or the native scatter viewer:

```powershell
pip install -r requirements-examples.txt
```

Tkinter is **optional**: it is used by the native photo viewer (`open_photo` action) and by the native scatter viewer (`open_scatter` action on a `scatter_2d` block). When it is unavailable, the photo viewer falls back to opening the URL in the system browser; the scatter viewer cannot fall back and reports the action as unavailable.

Tkinter is part of the Python standard library and is **not installable via `pip`**, so it does not appear in `requirements-examples.txt`. Its availability depends on how Python was built:

| Platform | How to get it |
|---|---|
| Windows (python.org installer) | Bundled by default (keep the "tcl/tk and IDLE" component enabled). |
| macOS (python.org installer) | Bundled by default. |
| Linux (Debian/Ubuntu) | `sudo apt install python3-tk` |
| Linux (Fedora) | `sudo dnf install python3-tkinter` |
| Conda | `conda install tk` |

### Other examples

```powershell
python .\main.py --spec .\mocks\operations.json --view dashboard
python .\main.py --spec .\mocks\voyager.json --view panel
python .\main.py --spec .\mocks\voyager.json --view compact
python .\main.py --spec .\mocks\scatter_demo.json --view dashboard
python .\main.py --example voyager
python .\main.py --example voyager --view panel
python .\main.py --example voyager --action open_photo
python .\main.py --example voyager --open-photo
python .\main.py --example voyager --open-scatter
python .\main.py
```

If `--spec` is omitted, `main.py` uses a built-in demo payload (spec + data + sync embedded in code).
If `--example voyager` is provided, `main.py` builds the three inputs from the configured cache directory via `examples/voyager/adapter.py`.

## Views

Available view modes:

- `dashboard`
- `panel`
- `compact`

## Public API

```python
from rich_ui import Theme, ViewMode, find_data_issues, render
```

Example:

```python
import json
from pathlib import Path

from rich.console import Console

from rich_ui import Theme, ViewMode, find_data_issues, parse_spec, render

spec = json.loads(Path("mocks/voyager.json").read_text(encoding="utf-8"))
data = json.loads(Path("mocks/voyager.data.json").read_text(encoding="utf-8"))
sync = json.loads(Path("mocks/voyager.sync.json").read_text(encoding="utf-8"))

frame = parse_spec(spec)
for issue in find_data_issues(frame, data):
    print(f"warning: {issue.message}")

console = Console()
console.print(render(frame, data=data, sync=sync, view=ViewMode.DASHBOARD, theme=Theme()))
```

`data` and `sync` are both optional — if a `bind` is missing or malformed, the offending block is rendered as a placeholder and the rest of the frame keeps working.

## DSL overview

The external input format is a dictionary-shaped DSL with a closed vocabulary. The DSL describes only **structure**: every block that consumes data declares a `bind` key.

Supported block types:

- `frame` — root container with named slots
- `stack` — horizontal or vertical composition
- `table` — bound to a list of homogeneous records
- `panel` — bound to a list of items (strings or styled segments)
- `photo_card` — bound to a single photo descriptor
- `scatter_2d` — bound to a 2D scatter payload (center + tracks of `x,y,z` points)

The DSL also supports responsive layout hints:

- `layout.span` on blocks, using a 12-column grid
- `layout.min_width` on blocks
- `layout.equal_height` on `stack` blocks
- `responsive` on `stack` blocks to switch between `row` and `column`
- `actions` on blocks to expose explicit runtime intents

Minimal example:

```json
{
  "type": "frame",
  "title": "Demo",
  "slots": {
    "body": [
      {
        "type": "stack",
        "direction": "row",
        "children": [
          { "type": "table", "title": "Services", "bind": "services" },
          { "type": "panel", "title": "Update",   "bind": "update"   }
        ]
      }
    ]
  }
}
```

Companion data file:

```json
{
  "services": [
    { "Name": "api",    "Status": "UP"       },
    { "Name": "worker", "Status": "DEGRADED" }
  ],
  "update": [
    "api: updated 15s ago",
    "worker: updated 60s ago"
  ]
}
```

Companion sync file (optional):

```json
{
  "services": {
    "source": "service-monitor",
    "updated_at": "2026-04-29T11:44:10Z",
    "interval_seconds": 15
  }
}
```

## Data shapes per block type

| Block type | `data[bind]` shape | Notes |
|---|---|---|
| `table` | `[{col1: v1, col2: v2}, ...]` — list of homogeneous records | Column order is taken from the first record's key order |
| `panel` | `[item, item, ...]` where each item is a string, `{"text": "...", "style": "..."}`, or `{"segments": [{"text", "style"}, ...]}` | Items can be heterogeneous |
| `photo_card` | `{"title": "...", "published"?: "...", "url"?: "...", "image_url"?: "..."}` | `title` is required |
| `scatter_2d` | `{"center"?: {...}, "tracks": [{"label"?, "caption"?, "marker"?, "style"?, "history_marker"?, "history_style"?, "samples"?: [...], "current"?: {...}}, ...]}` | Each `samples[i]` and `current` carries numeric `x, y, z` |

## Sync shape

```json
{
  "source": "service-monitor",
  "updated_at": "2026-04-29T11:44:10Z",
  "interval_seconds": 15
}
```

All fields are optional. When present, the renderer adds a footer like `service-monitor | updated 30s ago | every 15s` to the bound block.

## Error model

| Type | Cause | Behavior |
|---|---|---|
| `SpecError` | Malformed DSL (e.g. missing `bind`, invalid block type) | Raised at parse time, fails fast |
| `DataIssue` | Missing or malformed bind data at render time | Reported by `find_data_issues(...)`; the renderer shows a placeholder for the offending block and keeps rendering the rest of the frame |

A frame can therefore render with partial data — convenient for dashboards built on top of multiple independent services.

## Actions

Frames and blocks may declare optional `actions`:

```json
{
  "actions": [
    { "id": "open_photo", "label": "open photo viewer", "key": "T" }
  ]
}
```

The renderer shows the action hint directly in the related box, for example `Press T to open photo viewer`. When the loaded spec declares a compatible action, the runner also listens for that key after rendering.

If the DSL declares an action but the runtime has no handler for that `id`, the program:

- prints a startup warning
- renders the action as unavailable
- ignores direct execution for that action

`--action open_photo` and `--open-photo` remain available as direct execution shortcuts.

## Responsive layout

Responsive behavior is expressed in the DSL, not hardcoded in the renderer.

```json
{
  "type": "stack",
  "direction": "row",
  "layout": { "equal_height": true },
  "responsive": {
    "sm": "column",
    "md": "row",
    "lg": "row"
  },
  "children": [
    {
      "type": "table",
      "title": "Spacecraft",
      "bind": "spacecraft",
      "layout": {
        "span": { "sm": 12, "md": 12, "lg": 6 },
        "min_width": 60
      }
    },
    {
      "type": "panel",
      "title": "Update",
      "bind": "update",
      "layout": {
        "span": { "sm": 12, "md": 6, "lg": 3 },
        "min_width": 34
      }
    }
  ]
}
```

`layout.pin_footer` controls whether the meta/actions footer stays anchored at the bottom of a block when the renderer assigns extra height. Default: `true`.

Current breakpoints:

- `sm`: width `< 100`
- `md`: width `>= 100` and `< 160`
- `lg`: width `>= 160`

## Photo cards

For images or external media, prefer `photo_card` over a generic `panel`.

Spec:

```json
{
  "type": "photo_card",
  "title": "NASA Photo",
  "bind": "photo",
  "options": {
    "mode": "native_hint",
    "hint": "Best viewed in the Voyager native photo viewer"
  }
}
```

Data:

```json
{
  "photo": {
    "title": "Voyager Tour Montage",
    "published": "1998-10-30T14:58:30Z",
    "url": "https://images.nasa.gov/details/PIA01483",
    "image_url": "https://images-assets.nasa.gov/image/PIA01483/PIA01483~thumb.jpg"
  }
}
```

## Project structure

```text
rich-ui/
├── README.md
├── main.py
├── requirements.txt
├── requirements-examples.txt
├── docs/
│   ├── TECHNICAL_ANALYSIS.md
│   ├── FUNCTIONAL_ANALYSIS.md
│   └── DSL_REFERENCE.md
├── examples/
│   ├── common/
│   │   ├── photo_models.py
│   │   ├── photo_openers.py
│   │   └── tk_photo_viewer.py
│   └── voyager/
│       ├── README.md
│       ├── adapter.py
│       └── main.py
├── mocks/
│   ├── operations.json
│   ├── operations.data.json
│   ├── operations.sync.json
│   ├── scatter_demo.json
│   ├── scatter_demo.data.json
│   ├── scatter_demo.sync.json
│   ├── voyager.json
│   ├── voyager.data.json
│   └── voyager.sync.json
└── rich_ui/
    ├── __init__.py
    ├── dto.py
    ├── renderer.py
    ├── spec.py
    ├── theme.py
    └── view_mode.py
```

## Documentation

- [`docs/TECHNICAL_ANALYSIS.md`](docs/TECHNICAL_ANALYSIS.md)
- [`docs/FUNCTIONAL_ANALYSIS.md`](docs/FUNCTIONAL_ANALYSIS.md)
- [`docs/DSL_REFERENCE.md`](docs/DSL_REFERENCE.md)
- [`examples/voyager/README.md`](examples/voyager/README.md)
