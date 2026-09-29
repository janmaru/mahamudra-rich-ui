# Functional Analysis

## What the project does

`rich-ui` renders a structured UI description into terminal output using `rich`.

It is designed for cases where another system already knows the data and only needs a clean terminal presentation layer.

## What the inputs look like

The library accepts three independent inputs:

1. **spec** — a JSON-friendly DSL that describes only the *structure* of the UI (frame, slots, blocks, `bind` keys, layout, actions)
2. **data** — values for every block whose `bind` key appears in the spec
3. **sync** — per-bind freshness metadata (source, last update timestamp, interval)

The spec never carries values. The data never carries layout. The sync never carries content. Each plane is owned by a different actor:

| Plane | Owner | Lifecycle |
|---|---|---|
| spec | UI author | edited rarely (a release) |
| data | API/service | refreshed continuously |
| sync | orchestrator/cron | produced when each fetch is scheduled |

## Main concepts

### Frame

The root object. It represents the whole UI surface to render.

### Slot

A named section of the frame, such as:

- `header`
- `body`
- `bottom`

Slots are organizational containers.

### Panel

A vertical block of text items.

Typical use cases:

- summary information
- status messages
- updates
- notes

The actual lines come from `data[bind]`.

### Table

A structured block for row/column data.

Typical use cases:

- service lists
- telemetry rows
- metrics
- operational summaries

The records come from `data[bind]` as a list of homogeneous objects. Header columns are derived from the keys of the first record.

### Photo card

A block dedicated to images or external media. The image descriptor (title, published, URLs) comes from `data[bind]`.

### Scatter 2D

A 2D scatter plot rendered as ASCII on a fixed grid. Useful for spatial
overviews where the data is a small set of points: trajectory previews, sensor
locations, simple position maps.

Each scatter has:

- an optional `center` marker (e.g. the origin of a coordinate frame)
- one or more `tracks`, each with past `samples` and/or a `current` point
- a free-form `caption` per track and per center for legend annotations
  (the renderer never parses or computes units)

Typical use cases:

- mission trajectory previews
- 2D scatter clouds
- relative-position maps

### Stack

A composition block that places child blocks:

- horizontally with `direction = "row"`
- vertically with `direction = "column"`

This is the main layout primitive for arranging multiple blocks in the same area. Stacks have no `bind` of their own.

## Sync metadata

Every block bound to data may also have an optional `sync` entry, indexed by the same `bind` key. It carries:

- `source` — human-readable provenance
- `updated_at` — ISO-8601 timestamp of the last fetch
- `interval_seconds` — expected refresh cadence

When present, the renderer adds a freshness footer like `service-monitor | updated 30s ago | every 15s` to the bound block.

Use cases:

- source tracking
- freshness display
- mixed synchronization cadences (one bind every 15 s, another every hour)

Example:

- one table refreshes every 15 seconds
- one status panel refreshes every 60 seconds
- one summary panel refreshes every 15 minutes

All three can appear in the same frame while preserving their own refresh identity, because each bind has its own sync entry.

## Update panel strategy

An `Update` panel can be placed anywhere, including inside a `stack`. Recommended model:

- per-bind sync metadata is the source of truth
- an `Update` panel is a user-facing summary computed from that metadata
- the orchestrator that produces `sync` can also produce an aggregated `update` bind for the Update panel to consume

That keeps business data, freshness, and the optional aggregated summary clearly separated.

## Typical flows

### Flow 1: render a static spec + data file pair

1. Load `mocks/voyager.json` (spec)
2. Auto-discover or load `mocks/voyager.data.json` (data) and `mocks/voyager.sync.json` (sync)
3. Pass them to `render(...)`
4. Print the result with `rich.console.Console`

### Flow 2: upstream system builds the data and sync

1. The spec is authored by the UI team and committed in the repo
2. An orchestrator schedules the API calls
3. For each bind, the orchestrator produces the `data` payload and a matching `sync` entry
4. `rich-ui` validates and renders them together

### Flow 3: mixed synchronization dashboard

1. Different upstream sources produce different binds
2. Each bind carries its own sync metadata
3. The renderer displays the blocks together with per-bind freshness footers
4. An optional `Update` panel summarizes the sync map

## Error handling

| Cause | Effect |
|---|---|
| Malformed spec | `SpecError` is raised; the program fails fast. The spec is a contract. |
| Missing or malformed bind data | A `DataIssue` is reported; the offending block renders as a placeholder; the rest of the frame still renders. |

This split lets a dashboard survive a temporary outage on a single service while still showing every other panel.

## Example user scenarios

### Operations dashboard

- service table
- incident summary panel
- update panel with bind-level cadence summaries

### Telemetry dashboard

- measurements table
- status panel
- source freshness panel

### CLI monitoring view

- compact rendering mode
- simple JSON inputs (spec + data + sync)
- no extra application framework

## Mock files in this repository

Two example pairs are provided:

- `mocks/voyager.json` + `mocks/voyager.data.json` + `mocks/voyager.sync.json`
- `mocks/operations.json` + `mocks/operations.data.json` + `mocks/operations.sync.json`

They demonstrate:

- nested stacks
- bound tables, panels, and photo cards
- per-bind sync metadata
- aggregated update information inside a stack

## What the project does not do

- fetch data from APIs
- transform business objects into specs or data
- maintain application state
- schedule refresh cycles

Those concerns belong to the caller or to another layer built on top of this package.
