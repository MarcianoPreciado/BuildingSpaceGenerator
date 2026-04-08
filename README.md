# BuildingSpaceGenerator

BuildingSpaceGenerator is a wireless-simulation workspace for commercial buildings. The original project centered on procedural floor-plan generation; the current V2 path shifts the system toward importing real building data from Quantum graph exports and running placement, RF estimation, and visualization on top of those imported floors.

## Current Direction

The project is now on a V2 architecture path where imported building datasets are the primary source of truth.

What this changes:
- Procedural generation is no longer the intended long-term center of the system.
- Quantum `.graph.json` exports are now importable as single-floor simulation inputs.
- Imported floors can flow through the existing sensor-placement, path-loss, and visualization stack.
- High-level site/building/location metadata is preserved on imported scenes.
- Room-level window presence and window sides are inferred from imported glazing.

The working architecture write-up for this direction is in [docs/architecture/architecture-v2.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture/architecture-v2.md).

## What Works Now

Implemented on the current V2 path:
- List floors from a Quantum graph export.
- Select a single floor for simulation.
- Import rooms, wall segments, doors, glazing, and floor metadata from Quantum graphs.
- Preserve site, building, floor, and location metadata from the source export.
- Infer room window metadata:
  - `has_windows`
  - `window_sides` as `N`, `E`, `S`, `W`
- Run sensor placement on imported floors.
- Run ITU-style multi-wall path-loss estimation on imported floors.
- Visualize imported scenes in the browser.

Important current limitations:
- The original `buildingspacegen visualize` and `buildingspacegen simulate` commands still target the procedural path.
- Raw customer `Sample Buildings/` exports should be treated as import/reference inputs, not as the normal simulation entry point.
- Imported scenes may currently produce zero viable links under the default placement/RF assumptions even when device placement succeeds.

## Repository Layout

Important top-level directories and files:
- [buildingspacegen](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen)
  - main Python package
  - contains the importer, pipeline, placement, path-loss, and visualization code
- [Sample Buildings](/Users/marcianopreciado/BuildingSpaceGenerator/Sample%20Buildings)
  - local Quantum sample datasets, screenshots, and schema examples
  - use these for importer development/reference only
  - do not use them as the standard simulation input path
- [data](/Users/marcianopreciado/BuildingSpaceGenerator/data)
  - RF materials, radio profiles, and other runtime configuration inputs
- [output](/Users/marcianopreciado/BuildingSpaceGenerator/output)
  - generated artifacts
  - `output/imported-buildings/` contains building-only imported scenes
  - `output/imported-scenes/` contains full imported scenes with devices and links
- [docs](/Users/marcianopreciado/BuildingSpaceGenerator/docs)
  - organized project documentation
- [README.md](/Users/marcianopreciado/BuildingSpaceGenerator/README.md)
  - top-level project overview and current workflows
- [AGENTS.md](/Users/marcianopreciado/BuildingSpaceGenerator/AGENTS.md)
  - repo guidance for coding agents
- [CLAUDE.md](/Users/marcianopreciado/BuildingSpaceGenerator/CLAUDE.md)
  - mirrored repo guidance for Claude-style agent workflows

## Documentation Layout

The main documentation has been moved out of the repo root and organized under [docs](/Users/marcianopreciado/BuildingSpaceGenerator/docs):

- [docs/vision](/Users/marcianopreciado/BuildingSpaceGenerator/docs/vision)
  - project intent, early research, and the open-source survey
- [docs/architecture](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture)
  - original architecture, V2 architecture, review material, and track specs
- [docs/implementation](/Users/marcianopreciado/BuildingSpaceGenerator/docs/implementation)
  - track-specific implementation and quickstart notes
- [docs/history](/Users/marcianopreciado/BuildingSpaceGenerator/docs/history)
  - change history and historical notes

Key documents:
- [docs/vision/intent.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/vision/intent.md)
- [docs/architecture/architecture.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture/architecture.md)
- [docs/architecture/architecture-v2.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture/architecture-v2.md)
- [docs/architecture/track-specs.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture/track-specs.md)
- [docs/implementation/TRACK_C_QUICKSTART.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/implementation/TRACK_C_QUICKSTART.md)

## V2 Import Model

Imported Quantum scenes currently preserve:
- site name and site directory
- project state and feature access when present
- building ID and building/site relationships
- floor name, level, elevation, height, slab depth, ceiling height
- location latitude, longitude, and elevation when present
- building `relativeNorth`
- room display names and source IDs
- room window presence and window sides

Ownership fields are reserved in importer metadata, but the current sample exports do not populate owner/organization data.

## Quick Start

### 1. Setup

Create or use the local virtual environment and install the package:

```bash
cd /Users/marcianopreciado/BuildingSpaceGenerator
/opt/homebrew/bin/python3.13 -m venv .venv
cd buildingspacegen
../.venv/bin/pip install -e '.[dev]'
cd ..
```

### 2. Generate Sanitized Building Artifacts

The importer stage creates building-only artifacts under `output/imported-buildings/`. Those sanitized outputs are the preferred inputs for placement and simulation.

If you need to refresh those imports from a Quantum export, use the importer workflow once and then keep working from `output/imported-buildings/`.

### 3. Simulate From Sanitized Building Artifacts

This is the normal post-import workflow:
- load a building-only scene from `output/imported-buildings/`
- procedurally place devices from the seed and placement rules
- run ITU/path-loss and the single-run simulation
- launch the browser

```bash
.venv/bin/buildingspacegen simulate-scene \
  --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" \
  --seed 42 \
  --port 8000
```

For placement-only visualization without the single-run simulation filter:

```bash
.venv/bin/buildingspacegen visualize-scene \
  --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" \
  --seed 42 \
  --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

### 4. Optional: Import A Raw Quantum Export Directly

These commands still exist for importer work, but they should not be your normal simulation entry point for sensitive customer datasets. Prefer `visualize-scene` and `simulate-scene` with sanitized files in `output/imported-buildings/`.

Use:

```bash
.venv/bin/buildingspacegen simulate-imported \
  --graph "Sample Buildings/Millrock Office.graph.json" \
  --floor "Floor 1" \
  --seed 42 \
  --port 8000
```

For a placement-only browser view without the single-run simulation filter, use:

```bash
.venv/bin/buildingspacegen visualize-imported \
  --graph "Sample Buildings/Millrock Office.graph.json" \
  --floor "Floor 1" \
  --seed 42 \
  --port 8000
```

### 5. Preferred Sanitized Post-Import Workflow

If you already have a sanitized building-only artifact in `output/imported-buildings/`, use that as the input to placement and simulation. This is now the preferred simulation path.

Placement stage:
- procedural
- seed-based
- fast to regenerate
- not intended to be canonical saved source data

Simulation stage:
- starts from the imported building scene
- places devices procedurally
- computes path-loss
- optionally runs the single-run simulation filter

Placement-only visualization from a building-only scene:

```bash
.venv/bin/buildingspacegen visualize-scene \
  --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" \
  --seed 42 \
  --port 8000
```

Placement plus simulation from a building-only scene:

```bash
.venv/bin/buildingspacegen simulate-scene \
  --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" \
  --seed 42 \
  --port 8000
```

## Output Types

There are now two different imported-output styles in the repository:

- `output/imported-buildings/...`
  - building-only scene
  - includes geometry and metadata
  - does not include devices or links
- `output/imported-scenes/...`
  - full simulation scene
  - includes geometry, devices, radio profiles, and links
  - use this for browser visualization if you want equipment to appear

Cheap generated outputs:
- Device placement is procedural and seed-based.
- Placement is intended to be fast and repeatable for a given building import.
- Placement and simulation outputs do not need to be treated as canonical source data.
- The imported building/floor data remains the durable source of truth.

## Imported Building Artifacts

The sample Quantum files under [Sample Buildings](/Users/marcianopreciado/BuildingSpaceGenerator/Sample%20Buildings) were used to validate the importer and produce sanitized building artifacts in `output/imported-buildings/`.

Imported defaults currently include:
- `AIPO - T34 #100` -> `Floor 0`
- `Building G` -> `Floor 0`
- `Demo - Commercial Building` -> `Floor 0`
- `Kajima 11th Floor` -> `Floor 0`
- `Millrock Office` -> `Floor 1`
- `Mission College` -> `Floor 0`
- `Panasonic - Site 4` -> `Floor B1`
- `Rathe Associates HQ` -> `Floor 0`

## Notes On Recent Fixes

Recent importer fixes on the V2 path:
- corrected Quantum wall reconstruction to follow the ordered boundary loop instead of raw vertex ID order
- preserved high-level site/building/location metadata in imported scene metadata
- added room window-side inference from exterior glazing
- added tests to verify imported wall segments lie on room boundaries

## Next Steps

Planned next steps for V2:
- add UI support for selecting which floor to import
- surface imported metadata in the browser inspector/sidebar
- improve material inference for interior partitions without explicit constructions
- continue refactoring toward a canonical imported-scene model described in [docs/architecture/architecture-v2.md](/Users/marcianopreciado/BuildingSpaceGenerator/docs/architecture/architecture-v2.md)
