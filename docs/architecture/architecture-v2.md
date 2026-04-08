# BuildingSpaceGenerator V2 Architecture

## Context

The original architecture treats procedural floor-plan generation as the primary entry point:

`generate_building(...) -> place_sensors(...) -> compute_path_loss(...) -> visualize(...)`

That is no longer the right center of gravity for this project.

The new primary asset is a corpus of real building datasets in the Quantum graph schema. Those datasets already contain the floor geometry, space boundaries, walls, openings, floor metadata, and enough construction data to drive visualization, sensor placement, and RF estimation. V2 should therefore make imported building data the canonical source of truth and demote procedural generation to an optional legacy adapter.

The goal is not "better generation." The goal is a simulation platform that can:

1. Ingest real building/floor datasets.
2. Normalize them into a stable simulation scene model.
3. Run placement, RF/path-loss, and visualization on top of that model.
4. Support batch Monte Carlo across a catalog of imported floors.

## What I Verified From The Sample Quantum Graphs

I analyzed:

- `Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json`
- `Sample Buildings/Panasonic - Site 4/Panasonic - Site 4.graph.json`
- `Sample Buildings/Models.ts`

### Structural findings

- The graph root is a `Site`.
- The file is a flat node list plus a root object:
  - `rootType`
  - `root`
  - `nodes[]`
- Nodes are typed by `__typename`, not by a separate `type` field.
- Relevant topology chain is:
  - `Site -> Building -> Floor -> Zone -> Surface -> Shape -> Vertex`

### Geometry findings

- A usable room/zone footprint comes from the zone's `Boundary` surface.
- That `Boundary` surface owns a closed `Shape`.
- That `Shape` owns ordered `Vertex` objects with `(x, y, z)` coordinates.
- In both sample datasets, every usable zone has exactly one boundary polygon.
- The small number of zones without a boundary are non-simulation artifacts such as outdoor/environment/mechanical placeholders and should be filtered out by import policy.

### Wall findings

- Each `Wall` surface is anchored to exactly one boundary vertex.
- For every usable zone in both datasets:
  - number of wall surfaces == number of boundary edges
- That means wall `i` can be reconstructed as:
  - `boundary_vertex[i] -> boundary_vertex[i+1]`
- This is strong enough to build deterministic wall segments without guessing.

### Opening findings

- Doors, windows, and rolling doors are separate child surfaces:
  - `Door`
  - `Glazing`
  - `GarageDoor`
- They attach to a parent wall through `Adjacency` records:
  - parent surface is the wall
  - child surface is the opening
  - `adjacencyType` is typically `Pinned`
- Opening dimensions come from surface properties such as:
  - `width`
  - `height`
  - `thickness`
  - `subType`
- Opening position along the wall comes from adjacency offsets (`x`, `y`, `offset`).

### Construction/material findings

- Many exterior walls have explicit construction assemblies:
  - `Surface.layerSetID -> LayerSet -> Layer[] -> Media`
- Example assembly names/media in both samples:
  - `ExtWall Concrete`
  - `Concrete`
  - `Gypsum`
  - `stucco`
- Many interior wall surfaces do not have a `layerSetID`.
- Therefore V2 needs a two-stage RF material resolution strategy:
  1. direct assembly mapping when construction exists
  2. policy-based fallback inference when it does not

### Topology findings

- Shared inter-zone walls are not explicitly modeled as a single canonical wall object.
- Instead, adjacent zones may each contribute coincident boundary edges.
- In the Kajima sample this is simple enough for exact edge pairing in many cases.
- In the Panasonic sample, some normalized edges are shared by more than two zones after direct rounding, so a real topology pass is required:
  - snap
  - split at all incident vertices/openings
  - deduplicate into canonical barrier segments

### Metadata findings

- Building, floor, zone, and surface metadata is expressed through `Property` objects.
- Important values are already present:
  - building geometry units
  - floor `level`
  - floor `elevation`
  - floor `height`
  - zone `area`
  - zone `ceilingHeight`
  - surface dimensions
- Zone names are rich and domain-specific:
  - `Conference Room 1`
  - `Office 5`
  - `Lighting Laboratory 1`
  - `Machine Room`
  - `Lift 6`
  - `Hall 2`
  - `Anechoic Chamber`
- This is materially richer than the current fixed `RoomType` enum.

## Why The Current Architecture Is No Longer A Fit

The current architecture bakes in three assumptions that are now wrong:

1. `buildinggen` is the first-class source of building truth.
2. a small closed `RoomType` taxonomy is sufficient to represent spaces.
3. a wall is mostly a single-material line segment discovered during procedural generation.

That creates the wrong dependency direction:

- placement depends on procedural room typing
- path loss depends on simplified generated walls
- visualization depends on generated-room semantics

V2 should invert that:

- imported spatial scenes are the source of truth
- placement/RF/viz consume a canonical scene model
- procedural generation becomes just one possible scene source

## V2 Design Principles

1. Imported building graphs are canonical.
2. Single-floor simulation remains the primary scenario unit.
3. Raw source fidelity is preserved in metadata/provenance.
4. Downstream simulation modules depend on normalized scene interfaces, not on the import format.
5. Space classification is configurable and policy-driven, not hardcoded to a short enum.
6. Construction-to-RF mapping is explicit and overridable.
7. Procedural generation remains available only as a fallback source adapter.

## Recommended High-Level Architecture

### New dependency flow

```text
Quantum Graph / Other Source
            |
            v
      Source Importer
            |
            v
    Canonical Scene Builder
            |
            +--> Space Classification
            +--> Barrier / Opening Topology
            +--> RF Construction Mapping
            |
            v
       Simulation Scene
        /      |      \
       /       |       \
Placement   Path Loss   Visualization
       \       |       /
        \      |      /
         Monte Carlo Runner
```

### Recommended package layout

```text
buildingspacegen/
├── scene/
│   ├── model.py              # Canonical scene model
│   ├── topology.py           # Barrier/opening graph + snapping/splitting
│   ├── classification.py     # Space taxonomy + tagging
│   ├── materials.py          # Source construction -> RF profile mapping
│   └── adapters.py           # Legacy adapter to current Building model
├── sources/
│   ├── base.py               # SceneSource interface
│   ├── quantum/
│   │   ├── reader.py         # Parse .graph.json and build ID/type indexes
│   │   ├── extractor.py      # Site/building/floor/zone/surface extraction
│   │   ├── geometry.py       # Boundary/wall/opening reconstruction
│   │   ├── materials.py      # LayerSet/Layer/Media extraction
│   │   ├── catalog.py        # Imported dataset catalog and metadata index
│   │   └── importer.py       # Public importer API
│   └── procedural/
│       └── importer.py       # Adapter around current buildinggen
├── sensorplacer/             # Refactored to consume SimulationScene
├── pathloss/                 # Refactored to consume canonical barriers/openings
├── buildingviz/              # Refactored to visualize SimulationScene
├── montecarlo/
│   ├── scenario.py           # Scene selection and simulation inputs
│   └── batch.py              # Batch runner over imported catalog
└── pipeline.py               # Orchestrates sources -> scene -> placement -> RF
```

## Canonical Scene Model

The core mistake to avoid is importing Quantum data straight into the current procedural `Building/Floor/Room/WallSegment/Door` classes and calling that done. That is acceptable as a temporary bridge, but not as the end-state model.

The canonical model should preserve imported semantics explicitly.

### Suggested scene entities

```python
@dataclass
class SimulationScene:
    scene_id: str
    source: SceneSourceRef
    building: ImportedBuilding
    level: Level
    spaces: list[Space]
    barriers: list[Barrier]
    openings: list[Opening]
    metadata: dict

@dataclass
class SceneSourceRef:
    source_type: str          # "quantum_graph", "procedural", etc.
    source_path: str
    source_version: str | None
    root_id: str | None
    provenance: dict

@dataclass
class ImportedBuilding:
    id: str
    name: str
    raw_building_type: str | None
    footprint_bbox_m: tuple[float, float, float, float]
    metadata: dict

@dataclass
class Level:
    id: str
    name: str
    level_index: int | None
    elevation_m: float | None
    height_m: float | None
    metadata: dict

@dataclass
class Space:
    id: str
    name: str
    polygon: Polygon2D
    area_sqm: float
    height_m: float | None
    raw_category: str | None
    kind: SpaceKind
    tags: set[str]
    metadata: dict

@dataclass
class Barrier:
    id: str
    segment: LineSegment2D
    barrier_kind: BarrierKind   # exterior_wall, interior_partition, shaft_wall, facade, etc.
    side_a_space_id: str | None
    side_b_space_id: str | None
    construction: ConstructionAssembly | None
    openings: list[str]         # opening IDs
    metadata: dict

@dataclass
class Opening:
    id: str
    opening_kind: OpeningKind   # door, glazing, garage_door
    host_barrier_id: str
    position_along_barrier: float
    width_m: float
    height_m: float | None
    sill_height_m: float | None
    construction: ConstructionAssembly | None
    metadata: dict

@dataclass
class ConstructionAssembly:
    id: str
    name: str
    source_kind: str            # direct_quantum_layers, inferred_default, override
    layers: list[MaterialLayer]
    rf_profile_key: str | None
    metadata: dict

@dataclass
class MaterialLayer:
    media_name: str
    thickness_m: float | None
```

### Why this model is better than the current one

- It preserves raw source provenance.
- It separates `space semantics` from `placement policy`.
- It models barriers and openings explicitly for RF work.
- It supports imported materials/construction assemblies directly.
- It still adapts cleanly to the current visualizer shape.

## Space Classification Strategy

The current `RoomType` enum is too rigid for imported real-world buildings.

V2 should replace "room type as hardcoded enum" with two layers:

1. `SpaceKind`: a small canonical simulation category.
2. `tags`: flexible policy labels.

### Suggested `SpaceKind`

```text
workspace
meeting
circulation
restroom
service
mechanical
storage
lab
vertical_transport
loading
exterior
unknown
```

### Suggested classification inputs

- zone name
- zone color
- zone properties
- neighboring spaces
- floor name
- optional customer override rules

### Example policy behavior

- `Lift`, `Elevator`, `Stair` -> `vertical_transport`, exclude from sensors
- `Hall`, `Corridor`, `Lobby` -> `circulation`
- `Electrical Room`, `Machine Room`, `Mechanical` -> `mechanical`
- `Anechoic Chamber`, `Lighting Laboratory` -> `lab`
- `Office`, `Conference` -> `workspace` or `meeting`
- unmatched labels -> `unknown` with tags preserved

This is the right place to make placement configurable without corrupting source data.

## Quantum Import Pipeline

### Stage 1: Read and index

Build efficient lookup tables:

- `by_id`
- `by_typename`
- `children by relation ID`

This stage should be pure parsing with no inference.

### Stage 2: Extract site/building/floor candidates

- root `Site`
- selected `Building`
- selected `Floor`
- zones attached to that floor

Filter out:

- roof
- outdoor
- environment-only placeholders
- zones with no usable boundary polygon

### Stage 3: Build raw space geometry

For each zone:

1. find boundary surface
2. load its first shape
3. sort shape vertices by `index`
4. create closed polygon
5. derive ordered wall-edge list from polygon edges

This should be deterministic and cheap.

### Stage 4: Reconstruct raw wall/opening geometry

For each wall surface:

- map its anchor vertex back to the corresponding polygon edge
- create a provisional wall edge record
- attach door/window/opening child surfaces via `Adjacency`

### Stage 5: Canonical topology pass

This is the most important normalization stage.

It should:

1. snap nearly coincident vertices to a configurable tolerance
2. split long edges at all touching vertices/openings
3. merge coincident edges into canonical barrier segments
4. assign side A / side B spaces where possible
5. mark exterior segments when only one valid adjacent space exists

Do not rely on simple exact edge dedupe alone. The Panasonic sample proves that a planar-topology pass is required.

### Stage 6: Construction extraction and RF mapping

For each wall/opening:

1. extract direct construction assembly if present
2. resolve layer thicknesses from `Layer.thicknessProperty`
3. map `Media` names to RF material classes
4. if no direct construction exists, infer from policy rules

### Stage 7: Space classification

Apply the configurable classification rules and attach:

- `kind`
- `tags`
- placement eligibility flags

### Stage 8: Emit `SimulationScene`

At this point the downstream modules should not need to know the source was Quantum at all.

## RF / Path-Loss Architecture Changes

The current path-loss code assumes:

- building walls are already present
- each wall mostly maps to one material
- intersections are computed directly against those wall segments

V2 should instead operate on canonical barriers and openings.

### Recommended RF model changes

#### 1. Path loss consumes `Barrier` objects

The RF engine should trace against canonical barrier segments from `SimulationScene.barriers`.

#### 2. Openings override base wall loss

When a ray crosses a barrier:

- if the crossing falls in an opening span, use the opening RF assembly
- otherwise use the host wall RF assembly

#### 3. Construction assemblies become RF profiles

RF loss should be resolved from:

- direct assembly mapping if trustworthy
- inferred fallback if not

#### 4. Stochastic sampling caches per canonical barrier/opening

For each Monte Carlo run:

- sample barrier attenuation once
- sample opening attenuation once
- reuse for all links in that run

That preserves the reproducibility principle from the original architecture while matching imported geometry.

## Sensor Placement Architecture Changes

The current sensor placer is close to reusable, but it is too tied to:

- `RoomType`
- centroid heuristics that assume generated room programs
- wall selection over the old `Building` model

### Recommended placement changes

#### 1. Placement works from `SpaceKind` + tags

Rules should target semantic groups, not fixed room enums.

Example:

```yaml
exclude_tags:
  - mechanical
  - vertical_transport
  - exterior

space_policies:
  workspace:
    sensor_min_per_room: 1
    sensor_per_sqm: 0.02
  meeting:
    sensor_min_per_room: 1
    sensor_per_sqm: 0.03
  lab:
    sensor_min_per_room: 1
    sensor_per_sqm: 0.015
```

#### 2. Candidate walls come from canonical barriers

Only barriers that face the space and are mountable should be used.

#### 3. Controller placement uses scene topology, not only footprint centroid

Good controller candidates are:

- central circulation spaces
- large work areas
- spaces with high connectivity / low obstruction depth

The current centroid snap heuristic can remain as a fallback, but it should not be the only strategy.

#### 4. Placement policies must support overrides

Real imported buildings will always contain edge cases. Provide:

- per-space exclusion
- regex/name-based rules
- manual controller seed points if needed

## Visualization Architecture Changes

Visualization is worth preserving, but it should render imported semantics directly.

### Required changes

- render raw zone names, not only mapped room-type labels
- allow floor selection by imported floor ID/name
- visualize canonical barriers/openings rather than generated wall approximations
- optionally show imported floor image/background when available
- surface construction / RF class in tooltips
- preserve current link/device overlays

The existing 2D renderer can likely survive the transition through an adapter layer.

## Pipeline And CLI Changes

V2 should pivot the public API from "generate a building" to "load a scenario source."

### Recommended public API

```python
scene = load_scene(
    source="quantum_graph",
    path="Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json",
    floor_selector="Floor 0",
    import_policy=policy,
)

placement = place_devices(scene, rules, radio_profiles, seed=42)
graphs = compute_path_loss(scene, placement, material_db, frequencies_hz=[900e6, 2.4e9], seed=42)
```

### Recommended CLI

```text
buildingspacegen import-quantum <graph.json> --floor "Floor 0"
buildingspacegen simulate-scene <graph.json> --floor "Floor 0"
buildingspacegen visualize-scene <graph.json> --floor "Floor 0"
buildingspacegen batch-imported --catalog <dir> --filter building_type=office
```

## Migration Strategy

The right migration is not "delete everything and rewrite blindly." The right migration is staged.

### Phase 0: Immediate bridge

Objective: get imported sample floors running through the existing placement/RF/viz pipeline quickly.

Work:

1. Implement `sources.quantum.importer`.
2. Normalize one selected floor into a compatibility adapter that emits the current `Building/Floor/Room/WallSegment/Door` model.
3. Map raw zone labels into the current `RoomType` enum with a configurable classifier.
4. Store raw source metadata on rooms/walls/doors.

This is not the final architecture, but it gets useful output quickly.

### Phase 1: Canonical scene model

Objective: stop forcing imported data through a procedural-shaped model.

Work:

1. Introduce `scene.model`.
2. Refactor placement/pathloss/viz to accept `SimulationScene`.
3. Move procedural generation behind a `SceneSource` adapter.

### Phase 2: Imported catalog Monte Carlo

Objective: run Monte Carlo over real imported floors rather than synthetic footprints.

Work:

1. Build dataset catalog/index.
2. Add filtering and random sampling across imported floors.
3. Add scenario metadata export for downstream protocol simulation.

### Phase 3: Richer RF fidelity

Objective: use the imported construction data more accurately.

Work:

1. construction-to-RF mapping table
2. opening-aware barrier intersections
3. material inference overrides by customer/building family

## What I Would Preserve As-Is

- the dual-band RF concept
- stochastic wall attenuation per Monte Carlo run
- the general placement workflow order:
  - main controllers
  - secondary controllers
  - sensors
- the 2D visualizer investment
- the end-to-end pipeline idea

## What I Would Retire Or Demote

- `buildinggen` as the architectural center of the system
- procedural archetypes as the primary source of floor truth
- tight dependence on `RoomType`
- the assumption that walls are already known without topology reconstruction

## Concrete Recommendation

If the goal is to move this project toward the real business use-case as fast as possible, I would do this:

1. Keep the current procedural pipeline only as a legacy adapter.
2. Build a `QuantumGraphImporter` first.
3. Add a compatibility adapter so imported floors can immediately flow into existing placement/RF/viz code.
4. In parallel, introduce the canonical `SimulationScene` model and refactor consumers toward it.
5. Make the Monte Carlo runner sample from imported floor catalogs, not from generated archetypes.

That gets you near-term results without locking V2 into the wrong abstractions.

## Open Questions

These are the main decisions that will affect the first implementation pass:

1. Are future datasets always delivered as local `.graph.json` exports in this same Quantum object-graph shape, or do we also need to support direct API/database retrieval?
2. For V2, do you want Monte Carlo scenarios to remain strictly single-floor, with multi-floor graphs imported only as a source container from which one floor is selected?
3. For interior partitions that have no explicit `LayerSet`, do you already have another reliable field/source that distinguishes gypsum partitions from heavier walls, or should V2 start with configurable inference rules?
