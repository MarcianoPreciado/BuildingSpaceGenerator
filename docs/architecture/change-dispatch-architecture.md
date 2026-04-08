# Change Dispatch Architecture
## BuildingSpaceGenerator

**Prepared by:** Lieutenant Architect / Agent Manager
**Date:** 2026-04-06
**Inputs reviewed:** `intent.md`, `architecture.md`, `changes.md`, current code layout under `buildingspacegen/`

## Purpose

This document translates `changes.md` into a merge-safe execution plan for parallel agents. It is based on the current repository structure, not the aspirational future structure in `architecture.md`.

The goal is to let multiple agents implement the requested fixes in separate branches with minimal merge conflict risk and with clear integration sequencing.

## What Changed

`changes.md` introduces four functional deltas:

1. Door placement must move from midpoint-only to randomized wall placement with edge clearance.
2. Sensors/controllers must be wall-mounted with an explicit interior side, not room-centroid placement.
3. Device-count rules must move into YAML configuration.
4. BSP zoning must reject long-thin room rectangles and keep aspect ratios generally below 2:1.

## Architecture Impact Summary

These are not independent UI tweaks. They affect four connected layers:

1. `buildinggen`
   Door placement behavior and rectangular subdivision heuristics change here.
2. `sensorplacer`
   Device mounting moves from centroid-like room placement to wall-anchored placement.
3. `pathloss`
   Once devices have an explicit wall side, link geometry must not over-count or under-count the mounting wall.
4. `buildingviz`
   Door and device glyphs must render with orientation and sidedness.

The highest-risk coupling is wall-sided placement. If we only move device glyphs visually without defining sidedness in the shared model, the path-loss engine will remain semantically wrong.

## Shared Contract Decisions

These are the load-bearing contracts that should be established first.

### 1. Wall Orientation Convention

Adopt a directional convention for every `WallSegment`:

- `start -> end` defines the wall direction.
- `room_ids[0]` is the room on the left side of that direction.
- `room_ids[1]` is the room on the right side, or `None` for exterior walls.

This gives the system a deterministic definition of "side of wall" without adding ambiguity to the geometry model.

### 2. Device Mount Contract

Extend `Device` additively so existing callers do not break.

Recommended new optional fields:

- `position_along_wall: float | None = None`
- `mounted_side: str | None = None` where values are `"left"` or `"right"`
- `offset_from_wall_m: float = 0.0`

Semantics:

- `position` remains the rendered / simulation coordinate.
- `wall_id` remains required for wall-mounted devices.
- `mounted_side` identifies which side of the wall owns the device.
- `offset_from_wall_m` is a small interior offset used for rendering and RF geometry so the device is visibly and physically inside the room, not exactly on the wall centerline.

### 3. Door Placement Contract

Keep `Door.position_along_wall` as the canonical location, but define generation rules:

- Preferred rule: choose a random position with at least one door width of clearance from both wall ends.
- Fallback: if wall length is too short for that clearance, use `0.5`.

This is compatible with the current datamodel and serialization.

### 4. Path-Loss Interpretation Contract

For a wall-mounted device, the mounting wall is not automatically a crossed wall.

Interpretation rule:

- If the first infinitesimal movement from device origin goes into the device's owning room, the mounting wall is not counted.
- If a ray exits through the opposite side of that same wall, it is counted once.

Implementation note:

- The simplest stable method is to shift the RF origin by `offset_from_wall_m` into the owning room before running wall intersection tests.

## Proposed Module Shape

To reduce merge conflicts, introduce seams before the feature branches land.

### Building Generator

Current problem:

- Door logic and rectangular zoning logic both live in [buildingspacegen/buildinggen/generators/bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/bsp.py).

Proposed extraction:

- `buildingspacegen/buildinggen/postprocess/door_placement.py`
- `buildingspacegen/buildinggen/generators/layout_constraints.py`

Responsibilities:

- `door_placement.py`: legal door spans, random door placement, deterministic RNG use
- `layout_constraints.py`: max aspect ratio checks, slice scoring penalties, thin-zone repair helpers

After this extraction:

- Door work and BSP ratio work can proceed in parallel without both editing `bsp.py` heavily.

### Sensor Placement / Config

Add:

- `buildingspacegen/sensorplacer/config.py`
- `data/placement/device_placement_rules.yaml`

Responsibilities:

- YAML loading and validation
- default rule resolution
- optional building-type overrides later

### Visualization

Add:

- `buildingspacegen/buildingviz/renderers/glyphs.py`

Responsibilities:

- door swing geometry
- wall-tangent device placement glyph helpers
- isolated drawing logic so renderer feature work does not sprawl through the main render function

## YAML Configuration Architecture

Create a dedicated placement-rules file instead of hardcoding defaults in Python.

Recommended file:

- `data/placement/device_placement_rules.yaml`

Recommended shape:

```yaml
defaults:
  main_controller_per_sqft: 0.00004
  main_controller_wall_height_m: 2.0
  main_controller_prefer_center: true
  secondary_controller_per_sqft: 0.0002
  secondary_controller_wall_height_m: 2.0
  sensor_min_per_room: 1
  sensor_per_sqft: 0.002
  sensor_wall_height_m: 1.5
  sensor_min_spacing_m: 2.0
  wall_mount_offset_m: 0.12
  excluded_room_types:
    - corridor
    - elevator
    - stairwell

by_building_type:
  medium_office: {}
  large_office: {}
  warehouse: {}
```

Rationale:

- matches the current `PlacementRules` object
- keeps controller and sensor density in one authoritative place
- leaves room for archetype-specific tuning later without redesign

## Parallelization Strategy

### Phase 0: Prerequisite Contract Branch

This branch should land first. It is intentionally small and additive.

Branch:

- `codex/change-contract-seams`

Ownership:

- [buildingspacegen/core/device.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/core/device.py)
- [buildingspacegen/core/serialization.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/core/serialization.py)
- [buildingspacegen/buildinggen/postprocess/door_placement.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/postprocess/door_placement.py)
- [buildingspacegen/buildinggen/generators/layout_constraints.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/layout_constraints.py)
- [buildingspacegen/buildingviz/renderers/glyphs.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildingviz/renderers/glyphs.py)

Scope:

- add optional device mount fields
- extend serialization
- extract seam modules only
- no behavior change beyond preserving existing behavior through the new seams

Why it must land first:

- it removes the biggest merge hazard: multiple tracks editing the same central files for unrelated reasons

### Phase 1: Parallel Feature Branches

After Phase 0 lands, dispatch the following in parallel.

#### Track A: Door Placement Logic

Branch:

- `codex/change-door-placement`

Owns:

- [buildingspacegen/buildinggen/postprocess/door_placement.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/postprocess/door_placement.py)
- small wiring edits in [buildingspacegen/buildinggen/generators/bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/bsp.py)
- [buildingspacegen/tests/test_buildinggen/test_bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/tests/test_buildinggen/test_bsp.py)
- [tests/test_buildingviz/test_matplotlib.py](/Users/marcianopreciado/BuildingSpaceGenerator/tests/test_buildingviz/test_matplotlib.py) only for door fixture updates if needed

Deliverables:

- randomized door position with deterministic seed behavior
- end-clearance rule
- center fallback for short walls
- tests proving doors stay within legal spans

#### Track B: Wall-Mounted Devices + YAML Rules + Path-Loss Semantics

Branch:

- `codex/change-device-wall-mounting`

Owns:

- [buildingspacegen/sensorplacer/placer.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/sensorplacer/placer.py)
- [buildingspacegen/sensorplacer/api.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/sensorplacer/api.py)
- [buildingspacegen/sensorplacer/rules.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/sensorplacer/rules.py)
- [buildingspacegen/sensorplacer/config.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/sensorplacer/config.py)
- [data/placement/device_placement_rules.yaml](/Users/marcianopreciado/BuildingSpaceGenerator/data/placement/device_placement_rules.yaml)
- [buildingspacegen/pathloss/geometry.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/pathloss/geometry.py)
- [buildingspacegen/tests/test_sensorplacer/test_placement.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/tests/test_sensorplacer/test_placement.py)
- [buildingspacegen/tests/test_pathloss/test_intersection.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/tests/test_pathloss/test_intersection.py)
- [buildingspacegen/tests/test_core/test_serialization.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/tests/test_core/test_serialization.py)

Deliverables:

- sensors placed on actual room walls at random legal positions
- controllers also sourced from YAML density rules
- explicit interior side for each device
- no devices placed on building exterior
- RF intersection logic respects mounting side and offset
- deterministic placement maintained per seed

Notes:

- This is the largest track and should be owned by a stronger agent.
- Do not split YAML config into a separate branch; it touches the same API surface as device placement.

#### Track C: Visualizer Door and Device Glyphs

Branch:

- `codex/change-viz-mounted-glyphs`

Owns:

- [buildingspacegen/buildingviz/renderers/glyphs.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildingviz/renderers/glyphs.py)
- [buildingspacegen/buildingviz/renderers/matplotlib_2d.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildingviz/renderers/matplotlib_2d.py)
- [tests/test_buildingviz/test_matplotlib.py](/Users/marcianopreciado/BuildingSpaceGenerator/tests/test_buildingviz/test_matplotlib.py)

Deliverables:

- doors render as quarter-swing arcs rather than full circles
- sensors render tangent to the wall on the owning side
- controller glyphs remain visually distinct from sensors
- rendering still works when older scenes lack new optional mount metadata

Dependency:

- may begin after Phase 0, but final polish should be rebased after Track B if it uses new device metadata

#### Track D: BSP Aspect-Ratio Constraints

Branch:

- `codex/change-bsp-zone-ratios`

Owns:

- [buildingspacegen/buildinggen/generators/layout_constraints.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/layout_constraints.py)
- targeted wiring in [buildingspacegen/buildinggen/generators/bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/bsp.py)
- [buildingspacegen/tests/test_buildinggen/test_bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/tests/test_buildinggen/test_bsp.py)

Deliverables:

- penalize thin slices during parcel fill
- enforce preferred max aspect ratio around 2.0
- permit exceptions only where room program forces them
- tests over many seeds proving fewer corridor-like non-corridor zones

## Merge Conflict Risk Matrix

Low-risk parallel pairs after Phase 0:

- Track A + Track B
- Track B + Track D
- Track C + Track D

Moderate-risk pair:

- Track A + Track D

Reason:

- both still require a small integration touch in [buildingspacegen/buildinggen/generators/bsp.py](/Users/marcianopreciado/BuildingSpaceGenerator/buildingspacegen/buildinggen/generators/bsp.py)

Mitigation:

- keep `bsp.py` edits minimal and only as seam wiring
- put substantive logic in extracted helper modules
- merge Track D before Track A if both touch nearby generation flow

## Recommended Merge Order

1. `codex/change-contract-seams`
2. `codex/change-bsp-zone-ratios`
3. `codex/change-door-placement`
4. `codex/change-device-wall-mounting`
5. `codex/change-viz-mounted-glyphs`

Reasoning:

- contract branch creates safe seams
- BSP ratio work stabilizes room geometry before device placement relies on it
- door placement is localized once the seam exists
- device/pathloss work depends on the final wall and room semantics more than vice versa
- visualization should merge last because it adapts to the finalized metadata shape

## Acceptance Criteria By Change Request

### Door Placement

- doors are no longer always centered
- generated door center is at least one door width from each wall end when possible
- if not possible, center fallback is used
- renderer shows a quarter-swing arc, not a full brown circle

### Sensor / Controller Placement

- non-excluded rooms get at least `sensor_min_per_room`
- extra sensors are added when `sensor_per_sqft` requires more
- every placed device has a valid `wall_id`
- every wall-mounted device has an explicit interior side
- no sensor or controller is mounted to the building exterior
- rendered device markers are visually inside the owning room and tangent to the wall

### YAML Rules

- controller and sensor densities are loaded from YAML by default
- Python hardcoded defaults become fallback behavior only
- tests can inject alternate YAML fixtures without modifying source code

### Zone Proportions

- non-corridor rooms do not routinely exceed 2:1 aspect ratio across representative seed sweeps
- long-thin spaces are exceptions, not the common output pattern

## Test Strategy

Add or update tests in four groups:

1. Generator tests
   Validate legal door spans and room aspect ratio distribution over many seeds.
2. Placement tests
   Validate devices are wall-mounted, interior-sided, deterministic, and excluded from exterior walls.
3. Path-loss geometry tests
   Validate mounting wall count behavior using synthetic two-room and corridor-room fixtures.
4. Visualization tests
   Validate rendering does not crash with or without optional mount metadata.

## Agent Dispatch Recommendation

Use one lead agent for Phase 0, then four parallel workers:

1. Lead agent
   Deliver `codex/change-contract-seams`
2. Worker A
   Deliver `codex/change-door-placement`
3. Worker B
   Deliver `codex/change-device-wall-mounting`
4. Worker C
   Deliver `codex/change-viz-mounted-glyphs`
5. Worker D
   Deliver `codex/change-bsp-zone-ratios`

## Final Architectural Position

The changes should be treated as a wall-anchoring upgrade of the simulation model, not as isolated placement tweaks. The correct architecture is:

- additive shared device-mount metadata
- deterministic wall orientation semantics
- YAML-backed placement defaults
- seam extraction out of `bsp.py`
- path-loss interpretation based on owning-side offset
- visualization that renders the same semantics the simulator uses

That structure gives the agents clean ownership lines and keeps merge conflicts contained to small wiring edits instead of broad overlapping rewrites.
