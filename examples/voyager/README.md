# Voyager example

This example shows how to integrate `rich-ui` with a real external project without coupling the core library to that project's Python models.

The example reads cached JSON files produced by:

- `C:\Coding\Voyager-Explorer`

## How it works

1. `Voyager-Explorer` writes cache files such as `spacecraft.json`, `dsn.json`, and `weather.json`
2. `examples/voyager/adapter.py:build_voyager_from_cache(...)` loads those JSON files and returns a tuple `(spec, data, sync)`:
   - `spec` — the structural DSL with `bind` keys (no values inside)
   - `data` — the values for each `bind` (e.g. `data["spacecraft"]` is a list of records)
   - `sync` — per-bind freshness metadata (`source`, `updated_at`, `interval_seconds`)
3. `rich_ui.render(spec, data=data, sync=sync, ...)` renders the final terminal UI

The adapter does not embed values into the spec: spec, data and sync stay separate, in line with the three-plane model documented in [`docs/TECHNICAL_ANALYSIS.md`](../../docs/TECHNICAL_ANALYSIS.md).

## Run

From `C:\Coding\rich-ui`:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements-examples.txt
python .\main.py --example voyager
python .\main.py --example voyager --view panel
python .\main.py --example voyager --action open_photo
python .\main.py --example voyager --cache-dir C:\Coding\Voyager-Explorer\cache
python .\main.py --example voyager --open-photo
```

If the cache is empty, the example still renders placeholder blocks.

The `NASA Photo` box now declares an `open_photo` action with hotkey `T`, so after rendering you can press `T` from that screen to open the viewer. `--action open_photo` remains available as a direct shortcut. In the Voyager example the action also reuses the local cached `photo.bin` when available. If a future action is declared in the DSL without a runtime handler, the app warns at startup and marks it unavailable in the UI.

The photo opener uses:

- Tkinter for the native window
- Pillow for image loading and resize

If Tkinter is not available or the local photo file is missing, the opener falls back to the browser.

## Why this example matters

It demonstrates the intended architecture:

- `rich_ui/` stays generic
- project-specific mapping lives under `examples/`
- real data can be adapted into the DSL without importing project internals into the core library

