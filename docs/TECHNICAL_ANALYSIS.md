# Technical Analysis

## Purpose

`rich-ui` is a small rendering library that converts a structural UI DSL plus separate data and sync inputs into `rich` renderables.

The library is intentionally narrow in scope:

- it does not fetch data
- it does not own domain models
- it does not parse remote APIs
- it does not manage refresh loops

Its job is to validate three structured inputs and render them consistently.

## Three-plane model

```text
┌────────────┐    ┌────────────┐    ┌────────────┐
│    spec    │    │    data    │    │    sync    │
│ (structure)│    │  (values)  │    │ (freshness)│
└─────┬──────┘    └─────┬──────┘    └─────┬──────┘
      │                 │                 │
      ▼                 ▼                 ▼
   parse_spec      pass-through      pass-through
      │                 │                 │
      └─────────────────┼─────────────────┘
                        ▼
                     render(...)
                        ▼
                   RenderableType
```

| Plane | Source | Stability | Carries |
|---|---|---|---|
| **spec** | hand-written | stable | block types, `bind` keys, layout, actions |
| **data** | API/service | volatile | the actual values consumed by each `bind` |
| **sync** | orchestrator/cron | medium | `source`, `updated_at`, `interval_seconds` per bind |

The orchestrator that triggers data fetches knows when each call started and how often it must repeat. The API itself does not know — that is why `sync` is its own plane.

## High-level architecture

```text
spec (dict)        data (dict)         sync (dict)
    │                  │                  │
    ▼                  │                  │
parse_spec             │                  │
    │                  │                  │
    ▼                  ▼                  ▼
 Frame DTO  ──►  find_data_issues  ──►  warnings
    │                  │
    └──────────┬───────┘
               ▼
           renderer
               │
               ▼
        RenderableType
```

## Modules

### `rich_ui/spec.py`

Parses and validates the spec.

- validates the root `frame`
- validates slots
- validates supported block types
- requires `bind` on `panel`, `table`, `photo_card`, `scatter_2d`
- raises `SpecError` on invalid structures
- exposes `DataError` (used by the runtime layer for explicit data failures)

### `rich_ui/dto.py`

Defines the internal immutable data model:

- `Frame`, `Slot`
- `PanelBlock`, `TableBlock`, `PhotoCardBlock`, `Scatter2DBlock`, `StackBlock`
- `Scatter2DOptions`
- `BlockLayout`, `StackResponsive`
- `BlockMeta`, `Action`, `PanelItem`, `TextSegment`

Every data-carrying block exposes a `bind: str`. No legacy data fields (`columns`, `rows`, `items`, `photo`) live in the DTO.

### `rich_ui/renderer.py`

Transforms DTOs + data + sync into `rich` renderables.

- `render(spec, data, sync, view, theme)`
- `find_data_issues(frame, data) -> tuple[DataIssue, ...]` — non-fatal validation of bind data
- `DataIssue(bind, kind, message)` — value object exposed to callers
- composes slots, renders blocks, formats freshness footers, resolves responsive layout
- substitutes a placeholder for any block whose bind has issues — the rest of the frame keeps rendering
- keeps `rich`-specific logic isolated

Current rendering modes: `dashboard`, `panel`, `compact`.

### `rich_ui/theme.py`

Defines the styling surface for the renderer.

### `rich_ui/view_mode.py`

Defines the rendering mode enum.

## DSL contract

### Root

```json
{
  "type": "frame",
  "title": "Optional title",
  "slots": {}
}
```

### Slots

`slots` is a non-empty mapping where each key points to a list of blocks. Names such as `header`, `body`, `bottom` are conventions, not strict requirements.

### Blocks

Every data-carrying block declares a `bind`:

```json
{ "type": "panel",      "title": "Status",   "bind": "status"     }
{ "type": "table",      "title": "Services", "bind": "services"   }
{ "type": "photo_card", "title": "Photo",    "bind": "photo"      }
```

`stack` is composition-only:

```json
{
  "type": "stack",
  "direction": "row",
  "children": [ ... ]
}
```

### Responsive layout

```json
{
  "layout": {
    "span":      { "sm": 12, "md": 6, "lg": 3 },
    "min_width": 34,
    "equal_height": true
  }
}
```

Breakpoints based on terminal width:

- `sm`: `< 100`
- `md`: `>= 100` and `< 160`
- `lg`: `>= 160`

For row stacks, child blocks are placed on a 12-column grid and wrapped into new rows when their spans exceed the available row width. Blocks rendered in the same responsive row may also be normalized to the same visual height when `layout.equal_height` is enabled on the parent `stack`.

## Data shapes per bind

| Block type | `data[bind]` |
|---|---|
| `table` | `[{col1: v1, col2: v2}, ...]` — list of homogeneous records |
| `panel` | list of strings or `{text, style}` / `{segments: [...]}` items |
| `photo_card` | object with required `title`, optional `published`/`url`/`image_url` |
| `scatter_2d` | object with non-empty `tracks`; optional `center`; each track carries `samples` and/or `current` with numeric `x`, `y`, `z` |

## Sync shape

```json
{
  "source": "service-monitor",
  "updated_at": "2026-04-29T11:44:10Z",
  "interval_seconds": 15
}
```

All fields optional. Per-bind freshness footer is rendered when at least one field is present.

## Error model

| Type | When | Effect |
|---|---|---|
| `SpecError` | parse time | fail fast — the spec is the contract, programmer error |
| `DataIssue` | render time | non-fatal — placeholder + warning, frame still renders |

This separation matches the lifecycle of the inputs: the spec is authored once, the data and sync arrive at every refresh. A flaky service must not break the dashboard.

## Rendering behavior

### Dashboard view

- renders the frame as a single outer panel
- renders slots vertically
- renders row stacks via grid

### Panel view

- wraps each slot in its own panel
- emphasizes slot boundaries

### Compact view

- minimizes panel nesting
- useful for simpler terminal output

## Design decisions

### Why three planes

The same UI definition is consumed across many refreshes. Layout is stable; the data is volatile; the freshness metadata is owned by whoever scheduled the call. Mixing them would force the API to know about presentation, or the spec to ship with values it doesn't own.

### Why DTOs internally

Direct rendering from arbitrary dictionaries would make the renderer brittle and harder to maintain. The boundary parser converts JSON to DTOs once, and the renderer consumes only DTOs.

### Why per-bind sync

Each bind has its own refresh cadence (an alerts panel may refresh every 15 minutes while a DSN table refreshes every 10 seconds). A frame-level `meta` would lose this granularity and force a lowest-common-denominator refresh policy.

### Why `bind` keys instead of inline data

Inline data couples the spec to a single snapshot. With `bind`, the same spec can serve multiple refreshes, multiple data sources, multiple environments — just by swapping the data payload.

## Current limitations

- no schema export yet
- no automatic aggregate update block generation yet
- no tests yet
- no theming presets yet
- no custom block registry yet

## Recommended next steps

1. Add tests for parser and renderer (placeholder paths included)
2. Add optional generated `update` summaries from sync metadata
3. Add richer layout rules for named slots
4. Add JSON Schema export for spec/data/sync producers
