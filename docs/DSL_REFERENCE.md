# DSL Reference

## Overview

`rich-ui` accepts three independent inputs:

- a **spec** — a JSON-friendly DSL that describes only the *structure* of the UI
- a **data** payload — values for every block whose `bind` key appears in the spec
- a **sync** map — per-bind freshness metadata (source, last update, interval)

The spec never carries values; the data never carries layout; the sync never carries content.

The DSL itself is intentionally structured:

- root `frame`
- named `slots`
- nested blocks
- mandatory `bind` on every data-carrying block (`panel`, `table`, `photo_card`)
- optional responsive layout rules

## Root object

The root object must always be a `frame`.

```json
{
  "type": "frame",
  "title": "Optional title",
  "slots": {}
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `type` | string | yes | Must be `frame` |
| `title` | string | no | Frame title |
| `slots` | mapping | yes | Non-empty mapping of slot name to block list |
| `actions` | list | no | Frame-level actions |

## Slots

Each slot key maps to a list of blocks.

```json
{
  "slots": {
    "header": [],
    "body":   [],
    "bottom": []
  }
}
```

Slot names are free-form. Names like `header`, `body`, and `bottom` are conventions only.

## Block types

Supported block types:

- `panel`
- `table`
- `photo_card`
- `scatter_2d`
- `stack`

Every block that consumes data declares a `bind` key. The renderer resolves `bind` against the data payload at render time.

### Panel

Spec:

```json
{
  "type": "panel",
  "title": "Status",
  "bind": "status"
}
```

Data:

```json
{
  "status": ["Ready", "No active alerts"]
}
```

`status` items can also be styled segments:

```json
{
  "status": [
    {
      "segments": [
        { "text": "S", "style": "bold yellow" },
        { "text": " = Sun" }
      ]
    },
    "Plain text line"
  ]
}
```

### Table

Spec:

```json
{
  "type": "table",
  "title": "Services",
  "bind": "services"
}
```

Data:

```json
{
  "services": [
    { "Name": "api",    "Status": "UP"       },
    { "Name": "worker", "Status": "DEGRADED" }
  ]
}
```

The header row is built from the **keys of the first record** (insertion order). All records must share the same keys.

### Photo card

Spec:

```json
{
  "type": "photo_card",
  "title": "NASA Photo",
  "bind": "photo",
  "options": {
    "mode": "native_hint",
    "hint": "Best viewed in the native photo viewer"
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

### Scatter 2D

A scatter plot rendered as ASCII on a fixed grid. Useful for trajectory previews,
scatter clouds, or any 2D point distribution. The renderer is domain-agnostic:
labels, captions, and styles travel with the data.

Spec:

```json
{
  "type": "scatter_2d",
  "title": "Trajectory",
  "bind": "trajectory",
  "options": {
    "width": 60,
    "height": 16,
    "plane": "auto"
  }
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `options.width` | integer | no | Grid columns; defaults to terminal-aware size |
| `options.height` | integer | no | Grid rows; default `16` |
| `options.plane` | string | no | `auto` (default), `xy`, `xz`, `yz` |

When `plane` is `auto`, the two axes with the largest spread across all
`samples` and `current` points are chosen.

Data:

```json
{
  "trajectory": {
    "center": {
      "label": "Earth",
      "marker": "\u2299",
      "style": "bright_blue"
    },
    "tracks": [
      {
        "label": "VGR1",
        "caption": "167 AU",
        "marker": "\u25c6",
        "style": "bold bright_magenta",
        "history_marker": "\u00b7",
        "history_style": "magenta",
        "samples": [
          {"x": 1.2e9, "y": -3.4e9, "z": 0.5e9}
        ],
        "current": {"x": 1.5e9, "y": -3.6e9, "z": 0.6e9}
      }
    ]
  }
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `center` | object | no | Optional origin marker drawn at the grid center |
| `center.label` | string | no | Shown in the legend |
| `center.caption` | string | no | Free-form text appended to the legend (dim) |
| `center.marker` | string | no | First glyph used as marker (default `+`) |
| `center.style` | string | no | Rich style string |
| `center.shape` | string | no | Geometric shape token (see vocabulary below). Used by the native scatter viewer; ignored by the TUI renderer (which keeps using `marker`). |
| `tracks` | list | yes | Non-empty list of tracks |
| `tracks[].label` | string | no | Shown in the legend |
| `tracks[].caption` | string | no | Free-form text appended to the legend (dim) |
| `tracks[].marker` | string | no | First glyph for the current marker (default `*`) |
| `tracks[].style` | string | no | Rich style for marker and label in the legend |
| `tracks[].shape` | string | no | Geometric shape token for the `current` marker (see vocabulary below). Used by the native scatter viewer; ignored by the TUI renderer. |
| `tracks[].history_marker` | string | no | First glyph for past samples (default `·`) |
| `tracks[].history_style` | string | no | Rich style for past samples |
| `tracks[].history_shape` | string | no | Geometric shape token for the trail samples (see vocabulary below). Used by the native scatter viewer; ignored by the TUI renderer. |
| `tracks[].samples` | list | no | Past points; each must carry numeric `x`, `y`, `z` |
| `tracks[].current` | object | no | Latest point with numeric `x`, `y`, `z` |

A track must carry either `current` or a non-empty `samples` list. The renderer
draws history dots first, then the `current` markers on top, so the active
position is never hidden by the trail.

The legend strings (`label`, `caption`) are pure presentation: rich-ui does not
parse units. Whatever the producer puts in `caption` is appended verbatim, in a
dim style, after the label.

#### Shape vocabulary

The `shape`, `history_shape`, and `center.shape` fields accept one of ten
closed-vocabulary tokens. They standardize the geometry of the marker drawn by
the native scatter viewer (see `examples/common/tk_scatter_viewer.py`).

When `shape` is **omitted**, the viewer falls back to inferring the geometry
from the `marker` glyph (legacy behavior). When `shape` is **provided** and
valid, it takes precedence over the glyph. An invalid token is reported as a
`DataIssue` of kind `invalid_field`.

Tokens are **case-sensitive** and must be lowercase exactly as listed below
(e.g. `"diamond"`, not `"Diamond"`).

| Token | Meaning |
|---|---|
| `circle` | Filled disc |
| `ring` | Hollow circle (outline only) |
| `ringed` | Outer ring with a small inner filled disc (planet-like) |
| `diamond` | Filled diamond |
| `triangle_up` | Filled triangle, apex up |
| `triangle_down` | Filled triangle, apex down |
| `square` | Filled square |
| `cross` | Two crossing diagonal strokes |
| `star` | Five-pointed filled star |
| `dot` | Small filled disc (intended for trail samples) |

The TUI renderer (`rich`) does not use `shape`: it keeps printing the `marker`
glyph as before. The field is purely a hint to the native viewer.

### Stack

Stacks are composition-only and have no `bind` of their own.

```json
{
  "type": "stack",
  "direction": "row",
  "children": [
    { "type": "panel", "title": "A", "bind": "a" },
    { "type": "panel", "title": "B", "bind": "b" }
  ]
}
```

## Sync (freshness metadata)

`sync` is a separate map indexed by the same `bind` keys as `data`. It typically comes from the orchestrator that scheduled the data fetch.

```json
{
  "services": {
    "source": "service-monitor",
    "updated_at": "2026-04-29T11:44:10Z",
    "interval_seconds": 15
  }
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `source` | string | no | Human-readable provenance |
| `updated_at` | ISO-8601 string | no | Timestamp used for freshness display |
| `interval_seconds` | integer | no | Expected refresh cadence |

When at least one field is present, the renderer adds a footer line like `service-monitor | updated 30s ago | every 15s` to the bound block.

## Actions

Frames and blocks may define optional actions:

```json
{
  "actions": [
    { "id": "open_photo", "label": "open photo viewer", "key": "T" }
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `id` | string | yes | Stable action identifier used by the runtime |
| `label` | string | no | Human-readable label shown by the renderer |
| `key` | string | no | Single-character hotkey shown as `Press <key>` |

Actions are declarative. The DSL only announces that an action exists; the runtime decides whether and how to execute it.

If an action is declared in the DSL but no runtime handler exists for that `id`, the recommended behavior is:

- emit a warning at startup
- render the action as unavailable
- do not execute it when the hotkey is pressed

## Layout

Blocks may define an optional `layout` object.

```json
{
  "layout": {
    "span":      { "sm": 12, "md": 6, "lg": 3 },
    "min_width": 34,
    "pin_footer": true
  }
}
```

| Field | Type | Required | Notes |
|---|---|---:|---|
| `span` | mapping | no | Breakpoint-to-span mapping on a 12-column grid |
| `min_width` | integer | no | Minimum width required before fallback |
| `equal_height` | boolean | no | Meaningful on `stack`; normalizes child heights per row |
| `pin_footer` | boolean | no | On panel-like blocks, keeps meta/actions anchored at the bottom |

### Span rules

- valid breakpoint keys: `sm`, `md`, `lg`
- valid span values: `1` to `12`

### Footer pinning

`layout.pin_footer` controls whether meta/actions stay attached to the bottom of the block when the renderer assigns extra height. Default: `true`.

## Responsive

`stack` blocks may define a `responsive` object to change direction by breakpoint.

```json
{
  "responsive": {
    "sm": "column",
    "md": "row",
    "lg": "row"
  }
}
```

## Breakpoints

- `sm`: width `< 100`
- `md`: width `>= 100` and `< 160`
- `lg`: width `>= 160`

## Equal-height rows

Vertical contiguity is controlled in the DSL through `layout.equal_height` on a `stack`.

```json
{
  "type": "stack",
  "direction": "row",
  "layout": { "equal_height": true },
  "responsive": { "sm": "column", "md": "row", "lg": "row" },
  "children": [
    {
      "type": "table",
      "title": "Spacecraft",
      "bind": "spacecraft",
      "layout": { "span": { "sm": 12, "md": 12, "lg": 6 }, "min_width": 60 }
    },
    {
      "type": "panel",
      "title": "Update",
      "bind": "update",
      "layout": { "span": { "sm": 12, "md": 6, "lg": 3 }, "min_width": 34 }
    }
  ]
}
```

When `equal_height` is `true`, blocks in the same rendered row are measured and re-rendered to the same height.

## Validation rules

### `SpecError` (parse time)

- invalid block `type`
- missing `bind` on `panel`/`table`/`photo_card`
- invalid `span` values (out of `1..12`, unknown breakpoint)
- non-boolean `layout.equal_height` / `layout.pin_footer`
- duplicate action ids inside one block
- invalid action key length (must be a single character)
- `scatter_2d.options.plane` not in `{auto, xy, xz, yz}`
- non-positive `scatter_2d.options.width` / `scatter_2d.options.height`

### `DataIssue` (render time, non-fatal)

| Block | Issue kind | Cause |
|---|---|---|
| any | `missing` | `bind` key not present in `data` |
| `table` | `invalid_shape` | `data[bind]` is not a list |
| `table` | `empty` | record list is empty |
| `table` | `invalid_record` | a record is not an object |
| `table` | `inconsistent_keys` | a record has different keys than the first |
| `panel` | `invalid_shape` | `data[bind]` is not a list |
| `panel` | `invalid_record` | item is not a string nor an object with `text`/`segments` |
| `photo_card` | `invalid_shape` | `data[bind]` is not an object |
| `photo_card` | `missing_title` | `title` field missing or empty |
| `photo_card` | `invalid_field` | `published`/`url`/`image_url` is not a string when provided |
| `scatter_2d` | `invalid_shape` | `data[bind]` is not an object |
| `scatter_2d` | `invalid_field` | `center` or string fields are not strings/objects when provided |
| `scatter_2d` | `missing_tracks` | `tracks` is missing or empty |
| `scatter_2d` | `invalid_record` | a track has bad samples, malformed `current`, or no points at all |

When a block has any `DataIssue`, the renderer shows a placeholder ("data unavailable" + the issue message) and keeps rendering the rest of the frame.

## Recommended use

- keep business data outside the DSL
- keep freshness/orchestration metadata outside the DSL and outside the data
- use the DSL as a UI contract that does not change with each refresh
- use `meta` (sync) for freshness and provenance
- use `actions` for explicit terminal-friendly events
- use `layout` and `responsive` for terminal layout behavior
