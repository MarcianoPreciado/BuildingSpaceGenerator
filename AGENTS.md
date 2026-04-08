# BuildingSpaceGenerator

## Project Purpose
Wireless-simulation workspace for commercial buildings. The repo started around procedural floor-plan generation, but the current V2 path treats imported Quantum building graphs as the primary source of truth for geometry, placement, RF analysis, and visualization.

## Current Repo Direction
- Prefer the imported Quantum workflow over procedural generation when working on the main product path.
- Prefer sanitized building-only scene inputs in `output/imported-buildings/` for placement and simulation work.
- Keep procedural generation operational as a legacy/fallback path unless explicitly removing it.
- Single-floor simulation remains the active scope for imported scenes.
- Visualization, sensor placement, and ITU-style path-loss utilities must continue to work on imported floors.

## Documentation Layout
- `README.md` — repo overview, V2 workflow, directory map, and quick start
- `docs/vision/intent.md` — product goals and visualization requirements
- `docs/vision/initial-research.md` — early generator research
- `docs/vision/open-source-survey.md` — open-source survey
- `docs/architecture/architecture.md` — original procedural-first architecture
- `docs/architecture/architecture-v2.md` — current import-first architecture direction
- `docs/architecture/architectural-review-brief.md` — architecture review summary
- `docs/architecture/track-specs.md` — track specs and interface contracts
- `docs/implementation/` — track implementation notes and quickstarts
- `docs/history/changes.md` — historical notes and change log material

## Important Directories
- `buildingspacegen/` — core codebase
- `Sample Buildings/` — local Quantum sample datasets and screenshots, for importer development/reference only
- `data/` — RF materials and radio profile inputs
- `output/imported-buildings/` — preferred sanitized inputs for placement and simulation
- `output/imported-scenes/` — full imported scene exports with devices and links

## Current Implemented V2 Capabilities
- Quantum `.graph.json` floor listing and selection
- imported room, wall, door, and glazing reconstruction
- corrected wall reconstruction from ordered boundary loops
- imported site/building/floor/location metadata preservation
- room window inference via `has_windows` and `window_sides`
- imported-floor compatibility with sensor placement
- imported-floor compatibility with multi-wall path-loss
- first-class CLI commands for sanitized scene workflows: `visualize-scene` and `simulate-scene`
- browser visualization through exported scene JSON

## Current Limitations
- direct-from-Quantum commands still exist, but sanitized scene commands should be preferred for normal simulation runs
- some imported scenes may produce zero viable links under current default placement/RF assumptions

## Architecture Status
Original Phase 1 architecture is still present in code, but the active repo direction is V2 import-first. When in doubt, align new work with `docs/architecture/architecture-v2.md`.
