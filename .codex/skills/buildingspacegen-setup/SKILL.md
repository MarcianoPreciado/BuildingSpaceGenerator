---
name: "buildingspacegen-setup"
description: "Use when setting up, validating, or demoing the BuildingSpaceGenerator project, including venv creation, editable install, CLI verification, and browser-based simulate/visualize checks."
---

# BuildingSpaceGenerator Setup

## When to use
- Set up the local Python environment for `BuildingSpaceGenerator`.
- Reproduce the known-good install and CLI verification flow for this repo.
- Launch the browser UI for `simulate` or `visualize` and sanity-check the expected controls.

## Repo assumptions
- Project root is the current repository root.
- Python package root is `buildingspacegen/`.
- In this environment, `python3` may be too old (`3.9.6`). Prefer `/opt/homebrew/bin/python3.13` or any Python `>3.10`.
- Shell commands may print `pyenv: cannot rehash: /Users/marcianopreciado/.pyenv/shims isn't writable`. That warning did not block setup.

## Setup workflow
1. Start in the project root:
   ```bash
   cd /path/to/BuildingSpaceGenerator
   ```
2. Create the virtual environment with Python `>3.10`:
   ```bash
   /opt/homebrew/bin/python3.13 -m venv .venv
   .venv/bin/python --version
   ```
3. Install the local package and dev dependencies from the package directory:
   ```bash
   cd buildingspacegen
   ../.venv/bin/pip install -e '.[dev]'
   ```
4. Return to the project root and verify the CLI is installed:
   ```bash
   cd ..
   .venv/bin/buildingspacegen -h
   ```

## Expected CLI commands
- `simulate`: compare 900 MHz and 2.4 GHz behavior in the UI
  ```bash
  .venv/bin/buildingspacegen simulate --type medium_office --sqft 30000 --seed 1 --port 8000
  ```
- `visualize`: building layout and device placement sanity check
  ```bash
  .venv/bin/buildingspacegen visualize --type medium_office --sqft 30000 --seed 1 --port 8000
  ```

## Runtime checks
- If `pip install -e '.[dev]'` fails while resolving dependencies, it likely needs network access.
- If port `8000` is busy, check:
  ```bash
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  ```
- The clean successful startup output for `simulate` should look like:
  ```text
  Starting visualizer at http://localhost:8000
  INFO:     Started server process [...]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8000
  ```

## UI validation checklist
When `simulate` is open at `http://localhost:8000`, expect:
- Left side panel and main building visualization on the right.
- Frequency band selector that determines which links are shown.
- Link filter with min/max RX power sliders.
- Display options checkboxes for:
  - viable links only
  - sensors
  - secondary controllers
  - main controllers
  - links
  - room labels
- Generate scene section with `type`, `sqft`, and `seed`, plus a generate button.
- Statistics section showing input parameters and useful stats such as device counts and viable links.
- Room type legend showing room colors.

## Notes
- Prefer invoking the CLI as `.venv/bin/buildingspacegen` from the project root.
- `simulate` and `visualize` use the same generation arguments.
- If a future setup uses a different Python `>3.10` interpreter, substitute it for `/opt/homebrew/bin/python3.13`.
