# Parallel Track Dispatch Specs
## Building Space Generator & Wireless Sensor Network Simulation Platform

**Issued by:** Mr. Preciado (Master Architect)
**Date:** 2026-04-05
**Target model:** Claude Sonnet (all tracks)
**Execution mode:** Parallel — all four tracks launch simultaneously

---

## Preamble: Shared Interface Contract (ALL TRACKS READ THIS FIRST)

Before any track writes implementation code, the following shared interfaces MUST be understood by all agents. These are the connection points between independently developed subsystems. Every track MUST conform to these contracts exactly — they are the load-bearing joints of the system.

### P.1 Project Structure

All code lives under a single Python package root. The top-level layout is:

```
buildingspacegen/
├── pyproject.toml              # Single package, all subsystems
├── buildingspacegen/
│   ├── __init__.py
│   ├── core/                   # SHARED data model (Track A owns, all consume)
│   │   ├── __init__.py
│   │   ├── model.py            # Building, Floor, Room, WallSegment, Door, Material
│   │   ├── enums.py            # BuildingType, RoomType, WallMaterial, DeviceType
│   │   ├── geometry.py         # Point2D, Point3D, LineSegment2D, Polygon2D, BBox
│   │   ├── device.py           # Device, DevicePlacement, RadioProfile, PlacementRules
│   │   ├── links.py            # LinkResult, PathLossGraph (nx.Graph wrapper)
│   │   └── serialization.py    # to_dict / from_dict for all core types, JSON schema
│   ├── buildinggen/            # Track A
│   ├── sensorplacer/           # Track B (placement half)
│   ├── pathloss/               # Track B (path loss half)
│   ├── buildingviz/            # Track C
│   └── cli/                    # Track D
├── tests/
│   ├── test_core/
│   ├── test_buildinggen/
│   ├── test_sensorplacer/
│   ├── test_pathloss/
│   ├── test_buildingviz/
│   └── test_integration/
├── data/
│   ├── archetypes/             # YAML archetype configs (Track A produces)
│   │   ├── medium_office.yaml
│   │   ├── large_office.yaml
│   │   └── warehouse.yaml
│   ├── materials/              # RF material database (Track B produces)
│   │   └── rf_materials.yaml
│   └── radio_profiles/         # Radio hardware profiles (Track B produces)
│       ├── gen1_sensor.yaml
│       ├── gen2_sensor.yaml
│       └── main_controller.yaml
└── examples/
    └── quickstart.py
```

### P.2 Shared Core Data Model

Track A is responsible for implementing `core/`, but ALL tracks depend on it. The data model is defined in `architecture.md` sections 2.1–2.3. Here is the canonical interface that all tracks must code against. **If you need to add fields to these classes, add them as Optional with defaults so you don't break other tracks.**

#### P.2.1 Geometry Primitives (`core/geometry.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float: ...
    def to_3d(self, z: float = 0.0) -> Point3D: ...

@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float

    def to_2d(self) -> Point2D: ...
    def distance_to(self, other: Point3D) -> float: ...

@dataclass(frozen=True)
class LineSegment2D:
    start: Point2D
    end: Point2D

    def length(self) -> float: ...
    def intersects(self, other: LineSegment2D) -> bool: ...
    def intersection_point(self, other: LineSegment2D) -> Optional[Point2D]: ...
    def point_at_fraction(self, t: float) -> Point2D: ...  # t in [0, 1]

@dataclass
class Polygon2D:
    vertices: list[Point2D]   # Counter-clockwise winding

    def area(self) -> float: ...
    def centroid(self) -> Point2D: ...
    def contains(self, point: Point2D) -> bool: ...
    def edges(self) -> list[LineSegment2D]: ...
    def bounding_box(self) -> BBox: ...

@dataclass(frozen=True)
class BBox:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def width(self) -> float: ...
    def height(self) -> float: ...
    def area(self) -> float: ...
    def center(self) -> Point2D: ...
```

#### P.2.2 Enums (`core/enums.py`)

```python
from enum import Enum

class BuildingType(Enum):
    MEDIUM_OFFICE = "medium_office"
    LARGE_OFFICE = "large_office"
    WAREHOUSE = "warehouse"
    # Future Phase 2+:
    # RETAIL = "retail"
    # HOSPITAL = "hospital"
    # INDUSTRIAL = "industrial"

class RoomType(Enum):
    OPEN_OFFICE = "open_office"
    PRIVATE_OFFICE = "private_office"
    CONFERENCE = "conference"
    LOBBY = "lobby"
    CORRIDOR = "corridor"
    RESTROOM = "restroom"
    KITCHEN_BREAK = "kitchen_break"
    MECHANICAL = "mechanical"
    IT_SERVER = "it_server"
    STORAGE = "storage"
    WAREHOUSE_BAY = "warehouse_bay"
    LOADING_DOCK = "loading_dock"
    STAIRWELL = "stairwell"
    ELEVATOR = "elevator"
    # Extensible — new types added as needed

class WallMaterial(Enum):
    GYPSUM_SINGLE = "gypsum_single"          # 13mm drywall
    GYPSUM_DOUBLE = "gypsum_double"          # Double drywall partition
    CONCRETE_BLOCK = "concrete_block"         # 200mm CMU
    REINFORCED_CONCRETE = "reinforced_concrete"
    BRICK = "brick"
    GLASS_STANDARD = "glass_standard"
    GLASS_LOW_E = "glass_low_e"
    WOOD_DOOR = "wood_door"
    METAL_FIRE_DOOR = "metal_fire_door"
    ELEVATOR_SHAFT = "elevator_shaft"
    # Extensible

class DeviceType(Enum):
    MAIN_CONTROLLER = "main_controller"
    SECONDARY_CONTROLLER = "secondary_controller"
    SENSOR = "sensor"
```

#### P.2.3 Building Model (`core/model.py`)

```python
from dataclasses import dataclass, field
from typing import Optional, Iterator

@dataclass
class Material:
    name: str                         # Maps to WallMaterial.value
    thickness_m: float
    # RF properties live in the MaterialRFDatabase (Track B), not here.
    # This class describes the physical material only.

@dataclass
class WallSegment:
    id: str                           # Unique wall ID (e.g., "wall_042")
    start: Point2D
    end: Point2D
    height: float                     # meters
    materials: list[Material]         # Ordered outside-to-inside
    is_exterior: bool
    room_ids: tuple[str, Optional[str]]  # (room_a_id, room_b_id or None if exterior)

@dataclass
class Door:
    id: str
    wall_id: str                      # References WallSegment.id
    position_along_wall: float        # 0.0 to 1.0 fraction
    width: float
    height: float
    material: Material                # Door material (for RF — wood, metal, etc.)

@dataclass
class Room:
    id: str                           # Unique room ID (e.g., "room_017")
    room_type: RoomType
    polygon: Polygon2D
    floor_index: int
    wall_ids: list[str]               # References to WallSegment.id
    door_ids: list[str]               # References to Door.id
    ceiling_height: float
    metadata: dict = field(default_factory=dict)  # Extensible

    @property
    def area_sqft(self) -> float: ...
    @property
    def area_sqm(self) -> float: ...

@dataclass
class Floor:
    index: int
    rooms: list[Room]
    walls: list[WallSegment]
    doors: list[Door]
    elevation: float                  # Height above ground (meters)
    footprint: Polygon2D              # Outer boundary of this floor

@dataclass
class Building:
    building_type: BuildingType
    floors: list[Floor]
    footprint: Polygon2D              # Overall building footprint
    total_area_sqft: float
    seed: int
    metadata: dict = field(default_factory=dict)

    def all_rooms(self) -> Iterator[Room]: ...
    def all_walls(self) -> Iterator[WallSegment]: ...
    def all_doors(self) -> Iterator[Door]: ...
    def get_room(self, room_id: str) -> Room: ...
    def get_wall(self, wall_id: str) -> WallSegment: ...
    def get_walls_for_room(self, room_id: str) -> list[WallSegment]: ...
    def get_rooms_sharing_wall(self, wall_id: str) -> tuple[Room, Optional[Room]]: ...
```

#### P.2.4 Device Model (`core/device.py`)

```python
@dataclass
class RadioProfile:
    name: str                          # e.g., "gen1_sensor"
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    rx_sensitivity_dbm: float
    supported_frequencies_hz: list[float]  # e.g., [900e6, 2.4e9]
    # Future: noise_figure_db, bandwidth_hz, modulation, coding_gain

@dataclass
class Device:
    id: str                            # Unique device ID (e.g., "dev_042")
    device_type: DeviceType
    position: Point3D                  # (x, y, z) — z = wall mount height
    room_id: str                       # Which room it's in
    wall_id: str                       # Which wall it's mounted on
    radio_profile: RadioProfile        # Hardware characteristics
    metadata: dict = field(default_factory=dict)  # Extensible

@dataclass
class DevicePlacement:
    """Container for all placed devices in a building."""
    building_seed: int
    devices: list[Device]
    placement_rules: PlacementRules    # The rules used to generate this placement

    def get_devices_by_type(self, dtype: DeviceType) -> list[Device]: ...
    def get_devices_in_room(self, room_id: str) -> list[Device]: ...

@dataclass
class PlacementRules:
    main_controller_per_sqft: float
    main_controller_wall_height_m: float
    main_controller_prefer_center: bool

    secondary_controller_per_sqft: float
    secondary_controller_wall_height_m: float

    sensor_min_per_room: int
    sensor_per_sqft: float
    sensor_wall_height_m: float
    sensor_min_spacing_m: float

    excluded_room_types: list[RoomType] = field(default_factory=list)
```

#### P.2.5 Link / Path Loss Model (`core/links.py`)

```python
@dataclass
class LinkResult:
    tx_device_id: str
    rx_device_id: str
    frequency_hz: float
    distance_m: float
    fspl_db: float                     # Free-space path loss component
    wall_loss_db: float                # Total wall attenuation component
    path_loss_db: float                # Total = fspl + wall_loss
    rx_power_dbm: float                # Received signal after gains
    walls_crossed: int                 # Number of walls in path
    wall_details: list[dict]           # [{wall_id, material, attenuation_db}, ...]
    link_viable: bool                  # rx_power >= rx_sensitivity?
    link_margin_db: float              # rx_power - rx_sensitivity

class PathLossGraph:
    """Thin wrapper around nx.Graph with typed accessors."""
    def __init__(self): ...
    def add_link(self, link: LinkResult): ...
    def get_link(self, dev_a_id: str, dev_b_id: str, frequency_hz: float) -> Optional[LinkResult]: ...
    def get_viable_links(self, frequency_hz: float) -> list[LinkResult]: ...
    def get_device_neighbors(self, device_id: str, frequency_hz: float, min_margin_db: float = 0) -> list[str]: ...
    def to_networkx(self, frequency_hz: float) -> nx.Graph: ...
    @property
    def all_links(self) -> list[LinkResult]: ...
```

### P.3 JSON Interchange Schema

This is the canonical JSON format used between the backend (Tracks A, B, D) and frontend (Track C). All positions carry x, y, z even though Phase 1 renders only x, y. **Track C must consume this exact schema. Tracks A and B must produce it via `core/serialization.py`.**

```jsonc
{
  "building": {
    "building_type": "medium_office",
    "total_area_sqft": 25000,
    "seed": 42,
    "metadata": {},
    "floors": [{
      "index": 0,
      "elevation": 0.0,
      "footprint": [[0,0], [50,0], [50,30], [0,30]],  // [x,y] vertex list
      "rooms": [{
        "id": "room_001",
        "room_type": "open_office",
        "polygon": [[2,2], [20,2], [20,15], [2,15]],
        "area_sqft": 2906,
        "ceiling_height": 3.0,
        "wall_ids": ["wall_001", "wall_002", "wall_003", "wall_004"],
        "door_ids": ["door_001"]
      }],
      "walls": [{
        "id": "wall_001",
        "start": [2, 2],
        "end": [20, 2],
        "height": 3.0,
        "materials": [{"name": "gypsum_double", "thickness_m": 0.026}],
        "is_exterior": false,
        "room_ids": ["room_001", "room_002"]
      }],
      "doors": [{
        "id": "door_001",
        "wall_id": "wall_001",
        "position_along_wall": 0.5,
        "width": 0.9,
        "height": 2.1,
        "material": {"name": "wood_door", "thickness_m": 0.045}
      }]
    }]
  },
  "devices": [{
    "id": "dev_001",
    "device_type": "main_controller",
    "position": [25.0, 15.0, 2.0],  // [x, y, z]
    "room_id": "room_005",
    "wall_id": "wall_022",
    "radio_profile": "main_controller"  // Reference to profile name
  }],
  "radio_profiles": {
    "main_controller": {
      "name": "Main Controller",
      "tx_power_dbm": 10.0,
      "tx_antenna_gain_dbi": 5.0,
      "rx_antenna_gain_dbi": 5.0,
      "rx_sensitivity_dbm": -105.0,
      "supported_frequencies_hz": [900e6, 2.4e9]
    }
  },
  "links": {
    "frequency_hz": 900e6,           // Which band this link set is for
    "entries": [{
      "tx_device_id": "dev_001",
      "rx_device_id": "dev_002",
      "distance_m": 12.5,
      "path_loss_db": 68.3,
      "rx_power_dbm": -53.3,
      "walls_crossed": 2,
      "link_viable": true,
      "link_margin_db": 51.7
    }]
  },
  "simulation": null  // Populated by protosim (Phase 2+)
}
```

### P.4 Reproducibility Contract

Every random operation uses `numpy.random.Generator` created via `np.random.default_rng(seed)`. **No global random state. No `random.random()`. No unseeded generators.** The seed flows as:

- `Building.seed` → building generation RNG
- `Building.seed` → sensor placement RNG (same seed, but separate Generator instance seeded from `seed + 1` to avoid correlation)
- `Building.seed` + simulation run index → path loss stochastic sampling RNG (seeded `seed + 1000 + run_index`)

This means: same seed → same building → same device positions. Different Monte Carlo runs vary only the wall attenuation sampling.

### P.5 Performance Targets

| Operation | Target | Measured at |
|-----------|--------|-------------|
| Generate one building (medium office, 25k sqft) | < 1s | Track A |
| Place all devices in one building | < 0.5s | Track B |
| Compute full pairwise path loss graph (~200 devices) | < 5s | Track B |
| Full pipeline (generate → place → graph → JSON export) | < 10s | Track D |
| Render building in browser visualizer | < 2s initial load | Track C |

### P.6 Future Expansion Hooks (All Tracks Must Accommodate)

These features are NOT in Phase 1, but the code must not prevent their addition:

1. **Multi-floor buildings** — `Floor.index` and `Floor.elevation` exist. Generators produce one floor in Phase 1 but the model is multi-floor ready. Path loss across floors (floor penetration loss) is a future addition.
2. **Additional building types** — The archetype registry pattern (YAML + registry lookup) means new types are added without code changes.
3. **Ray tracing path loss** — `PathLossModel` is an abstract interface; multi-wall is one implementation. Ray tracing is another.
4. **3D visualization** — JSON carries z-coordinates. Phase 1 frontend ignores z; Phase 2 Three.js renderer uses it.
5. **Protocol simulation overlay** — The JSON schema has a `"simulation"` field (null in Phase 1). Track C's visualizer should render simulation data when present.
6. **IFC import** — Building model has enough structure to be populated from IFC files, not just from generators.
7. **Neural network training** — Batch Monte Carlo output (Track D) produces structured results suitable for ML pipelines.

---

## Track A: Core Data Model + BSP Building Generator

### Agent Instructions

You are implementing the foundational building generator subsystem. Your code is consumed by every other track. Correctness and interface stability are paramount.

### Scope

1. **`buildingspacegen/core/`** — The shared data model (geometry, enums, model, device, links, serialization). This is the single most critical deliverable — all other tracks import from here.
2. **`buildingspacegen/buildinggen/`** — The BSP floor plan generator with archetype parameterization.
3. **`data/archetypes/`** — YAML archetype configuration files for the three Phase 1 building types.
4. **`tests/test_core/`** and **`tests/test_buildinggen/`**

### Detailed Tasks

#### A.1 Core Data Model (`core/`)

Implement every class specified in Preamble sections P.2.1 through P.2.5 inclusive. These are canonical — follow the field names, types, and method signatures exactly. Use Shapely for the Polygon2D implementation internally (delegate `area()`, `centroid()`, `contains()` to shapely) but keep the public interface as defined.

**`core/serialization.py`**: Implement `to_dict()` and `from_dict()` class methods on every core dataclass, producing JSON conforming exactly to the schema in P.3. Use a single `serialize_building_scene(building, devices, links, radio_profiles)` top-level function that produces the full JSON document.

#### A.2 Enums and Room Type System

Implement all enums from P.2.2. Add a room type metadata registry:

```python
# In core/enums.py or a separate core/room_types.py
ROOM_TYPE_METADATA: dict[RoomType, dict] = {
    RoomType.OPEN_OFFICE: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 20.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.1,
    },
    RoomType.IT_SERVER: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.CONCRETE_BLOCK,
        "min_area_sqm": 10.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.02,
    },
    # ... all room types
}
```

This metadata drives material assignment in post-processing and informs Track B's sensor placement exclusions.

#### A.3 Archetype System

Each archetype YAML defines the statistical distribution of room types, sizes, and construction for a building type. Archetype files are loaded by the generator to parameterize the BSP.

**Schema for `data/archetypes/medium_office.yaml`:**

```yaml
building_type: medium_office
description: "DOE Commercial Reference: Medium Office (~53,600 sqft, 3 floors)"

footprint:
  aspect_ratio_range: [1.2, 2.0]       # width/depth ratio
  shapes: ["rectangle"]                  # Phase 1: rectangle only
  # Future: ["rectangle", "L", "U"]

floor:
  ceiling_height_m: 3.0
  corridor_width_m: 1.8

room_program:                            # Target distribution of floor area
  - room_type: open_office
    area_fraction: 0.55
    min_area_sqm: 30
    max_area_sqm: 200
  - room_type: private_office
    area_fraction: 0.10
    min_area_sqm: 10
    max_area_sqm: 20
  - room_type: conference
    area_fraction: 0.10
    min_area_sqm: 15
    max_area_sqm: 50
  - room_type: lobby
    area_fraction: 0.03
    min_area_sqm: 20
    max_area_sqm: 60
  - room_type: restroom
    area_fraction: 0.05
    min_area_sqm: 8
    max_area_sqm: 25
  - room_type: kitchen_break
    area_fraction: 0.04
    min_area_sqm: 15
    max_area_sqm: 40
  - room_type: mechanical
    area_fraction: 0.05
    min_area_sqm: 10
    max_area_sqm: 30
  - room_type: it_server
    area_fraction: 0.03
    min_area_sqm: 10
    max_area_sqm: 20
  - room_type: storage
    area_fraction: 0.03
    min_area_sqm: 5
    max_area_sqm: 15
  - room_type: stairwell
    area_fraction: 0.01
    min_area_sqm: 8
    max_area_sqm: 12
  - room_type: elevator
    area_fraction: 0.01
    min_area_sqm: 4
    max_area_sqm: 6

wall_construction:
  exterior: reinforced_concrete
  interior_default: gypsum_double
  overrides:                             # Room-type-specific wall upgrades
    it_server: concrete_block
    mechanical: concrete_block
    elevator: elevator_shaft
    stairwell: reinforced_concrete
```

Create similar files for `large_office.yaml` and `warehouse.yaml`. Research the DOE Commercial Reference Building specifications for realistic values: large offices are bigger footprints with higher open-office fractions; warehouses are dominated by a single large `warehouse_bay` zone (~80–90%) with small office/loading dock/mechanical zones around the perimeter.

Implement `buildinggen/archetypes/registry.py` to load all YAML files from `data/archetypes/` and look up by `BuildingType`.

#### A.4 BSP Generator

Implement `buildinggen/generators/bsp.py`:

1. **Footprint generation**: Given total sqft and archetype, compute a rectangular footprint with aspect ratio sampled from the archetype's range using the seeded RNG.
2. **Room program generation**: From archetype room_program, generate a list of `(RoomType, target_area_sqm)` tuples. The sum of target areas should be ~85-90% of floor area (rest is corridors).
3. **BSP subdivision**: Recursively partition the footprint rectangle. At each step, split the room list into two groups by cumulative target area. Choose split axis based on aspect ratio of the current rectangle. Add small seeded random perturbation (±5%) to the split position. Terminate when a partition contains exactly one room.
4. **Corridor insertion**: After BSP, insert a main corridor along the longest axis (width configurable from archetype). Re-adjust room boundaries that overlap the corridor.
5. **Room assignment**: Assign RoomType to each BSP leaf partition. Match partitions to room program entries by area (largest-to-largest pairing works well).
6. **Wall construction**: Create WallSegment objects along every room boundary. Adjacent rooms share a single wall (with both room IDs). Assign materials per archetype: exterior walls get exterior material, interior walls get `interior_default` unless one of the adjacent rooms has an override.
7. **Door placement**: Place one door per shared interior wall (at midpoint). Use wood_door material by default; use metal_fire_door for stairwells and mechanical rooms.
8. **Validation**: Every room must be reachable from the corridor via doors. No room is smaller than its `min_area_sqm`. Room type distribution is within 10% of archetype targets.

Implement `buildinggen/generators/base.py` with an abstract `BuildingGenerator` interface so treemap and genetic generators can be added later without changing the API.

#### A.5 Public API

`buildinggen/api.py`:

```python
def generate_building(
    building_type: BuildingType,
    total_sqft: float,
    num_floors: int = 1,          # Phase 1: always 1
    seed: int = 42,
    generator: str = "bsp",       # Future: "treemap", "genetic"
    archetype_overrides: Optional[dict] = None,
) -> Building:
    """Generate a complete building model."""
```

#### A.6 Tests

- **`test_core/test_geometry.py`**: Point distances, line intersection, polygon area/centroid/containment, edge extraction.
- **`test_core/test_serialization.py`**: Round-trip `to_dict()` → `from_dict()` for every core type. Validate JSON against P.3 schema.
- **`test_buildinggen/test_bsp.py`**: Generate medium_office, verify room count, area distribution within tolerance, all rooms reachable, no overlapping rooms, deterministic (same seed → same result).
- **`test_buildinggen/test_archetypes.py`**: Load each archetype YAML, verify all required fields present, room program fractions sum to ~1.0.

### Output Artifacts

| Artifact | Path |
|----------|------|
| Core data model | `buildingspacegen/core/*.py` |
| BSP generator | `buildingspacegen/buildinggen/` |
| Archetype configs | `data/archetypes/*.yaml` |
| Unit tests | `tests/test_core/`, `tests/test_buildinggen/` |
| pyproject.toml | `pyproject.toml` (with all dependencies) |

### Verification

After all code is written, run `pytest tests/test_core/ tests/test_buildinggen/ -v`. All tests must pass. Then generate one medium office building and pretty-print the JSON output to verify the schema matches P.3.

---

## Track B: Sensor Placer + Path Loss Engine

### Agent Instructions

You are implementing the device placement system and the RF path loss computation engine. You consume the Building model from `core/` (Track A) and produce DevicePlacement and PathLossGraph objects. Your primary consumers are Track C (visualizer) and Track D (CLI/batch runner).

**IMPORTANT**: You share `core/` with Track A. Do NOT create your own data model classes. Import `Device`, `DevicePlacement`, `RadioProfile`, `PlacementRules`, `LinkResult`, `PathLossGraph` from `buildingspacegen.core`. If Track A's implementations aren't available yet, write against the interface specs in Preamble P.2.4 and P.2.5 — they are the contract.

### Scope

1. **`buildingspacegen/sensorplacer/`** — Rule-based device placement engine
2. **`buildingspacegen/pathloss/`** — Multi-wall path loss model + graph construction
3. **`data/materials/rf_materials.yaml`** — RF attenuation database
4. **`data/radio_profiles/*.yaml`** — Radio hardware profile configs
5. **`tests/test_sensorplacer/`** and **`tests/test_pathloss/`**

### Detailed Tasks

#### B.1 RF Material Database (`data/materials/rf_materials.yaml`)

Encode the full attenuation table from architecture.md §6.1. Schema:

```yaml
materials:
  gypsum_single:
    description: "Single layer 13mm drywall"
    bands:
      2400000000:   # 2.4 GHz
        mean_attenuation_db: 3.0
        sigma_attenuation_db: 0.33
      900000000:    # 900 MHz
        mean_attenuation_db: 2.0
        sigma_attenuation_db: 0.33
  gypsum_double:
    bands:
      2400000000:
        mean_attenuation_db: 5.5
        sigma_attenuation_db: 0.50
      900000000:
        mean_attenuation_db: 4.0
        sigma_attenuation_db: 0.33
  # ... all materials from architecture.md §6.1
```

Implement `pathloss/materials.py`:

```python
class MaterialRFDatabase:
    @classmethod
    def from_yaml(cls, path: str) -> MaterialRFDatabase: ...

    def get_attenuation(
        self,
        material_name: str,
        frequency_hz: float,
        rng: np.random.Generator
    ) -> float:
        """Sample stochastic attenuation for one wall. max(0, Normal(μ, σ))."""

    def get_deterministic_attenuation(
        self,
        material_name: str,
        frequency_hz: float
    ) -> float:
        """Return the mean attenuation (for non-Monte-Carlo use)."""
```

**Stochastic attenuation contract**: Attenuation is sampled ONCE per wall per simulation run, NOT per link computation. The caller (graph builder) is responsible for pre-sampling a `dict[str, float]` mapping `wall_id → sampled_attenuation` before computing links, then passing that map into the link calculator. This is critical for Monte Carlo correctness.

#### B.2 Radio Profile Loader (`pathloss/radio.py`)

Load YAML files from `data/radio_profiles/` into `RadioProfile` dataclass instances. Implement defaults matching architecture.md §6.3 (gen1_sensor, gen2_sensor, main_controller). Create a `RadioProfileRegistry` that loads all profiles from a directory.

#### B.3 Sensor Placer (`sensorplacer/`)

Implement `sensorplacer/placer.py`:

```python
def place_devices(
    building: Building,
    rules: PlacementRules,
    radio_profiles: dict[DeviceType, RadioProfile],
    seed: int,
) -> DevicePlacement:
```

Algorithm (from architecture.md §2.2):

1. **Main Controllers first**: Count = `max(1, ceil(building.total_area_sqft / (1 / rules.main_controller_per_sqft)))`. If count == 1, find the wall position closest to the building footprint centroid. If count > 1, use k-means clustering on room centroids, then snap each cluster center to the nearest wall position.
2. **Secondary Controllers next**: Count = `ceil(building.total_area_sqft * rules.secondary_controller_per_sqft)`. Distribute to maximize minimum distance from existing controllers (greedy farthest-point). Snap to walls.
3. **Sensors last**: For each room (excluding `rules.excluded_room_types`): count = `max(rules.sensor_min_per_room, ceil(room.area_sqft * rules.sensor_per_sqft))`. Distribute evenly along room wall perimeter at `rules.sensor_wall_height_m`, respecting `rules.sensor_min_spacing_m`.

**Wall mounting**: A device is placed at a `Point3D(x, y, z)` where `(x, y)` is a point along a `WallSegment` (parameterized by `t` in [0, 1]) and `z` is the configured wall mount height. Store both the `Point3D` position and the `wall_id` + fractional position for future use.

Implement `sensorplacer/rules.py` with default PlacementRules presets:

```python
DEFAULT_RULES = PlacementRules(
    main_controller_per_sqft=1/25000,
    main_controller_wall_height_m=2.0,
    main_controller_prefer_center=True,
    secondary_controller_per_sqft=1/5000,
    secondary_controller_wall_height_m=2.0,
    sensor_min_per_room=1,
    sensor_per_sqft=1/500,
    sensor_wall_height_m=1.5,
    sensor_min_spacing_m=2.0,
    excluded_room_types=[RoomType.ELEVATOR, RoomType.STAIRWELL],
)
```

#### B.4 Path Loss Engine (`pathloss/`)

Implement `pathloss/models/multiwall.py`:

```python
class MultiWallPathLossModel:
    def __init__(self, material_db: MaterialRFDatabase): ...

    def compute_link(
        self,
        tx_device: Device,
        rx_device: Device,
        building: Building,
        wall_attenuations: dict[str, float],  # Pre-sampled: wall_id → dB
        frequency_hz: float,
    ) -> LinkResult:
        """
        Compute link budget between two devices.

        1. Euclidean distance between tx and rx positions (2D for Phase 1)
        2. FSPL = 20*log10(d) + 20*log10(f) - 147.55
        3. Find all walls intersected by the direct path (line-segment intersection)
        4. Sum pre-sampled attenuation for each intersected wall
        5. Total path loss = FSPL + wall_loss
        6. rx_power = tx_power + tx_gain + rx_gain - path_loss
        7. viable = rx_power >= rx_sensitivity
        """
```

Implement `pathloss/models/base.py` with abstract `PathLossModel` interface so ray tracing can be added later.

Implement `pathloss/geometry.py`: Ray-wall intersection. Given `LineSegment2D(tx_pos.to_2d(), rx_pos.to_2d())` and a list of `WallSegment`s from the building, return the list of walls whose line segments intersect the TX→RX ray. **Edge case**: A wall that contains a door — if the ray passes through the door portion of the wall, use the door's material attenuation instead of the wall's. Parameterize the door as occupying `[position - width/2/wall_length, position + width/2/wall_length]` along the wall and check if the intersection point falls within that range.

#### B.5 Graph Builder (`pathloss/graph.py`)

```python
def build_path_loss_graph(
    building: Building,
    placement: DevicePlacement,
    model: PathLossModel,
    material_db: MaterialRFDatabase,
    frequency_hz: float,
    seed: int,
    run_index: int = 0,
) -> PathLossGraph:
    """
    Build the complete pairwise path loss graph.

    1. Create RNG seeded with (seed + 1000 + run_index) per P.4 contract
    2. Pre-sample wall attenuations: for each wall in building, sample once
    3. For each device pair (N*(N-1)/2), compute LinkResult
    4. Store in PathLossGraph
    """
```

For dual-band support, the caller invokes this function twice (once per frequency) or the function accepts a list of frequencies and returns a dict of graphs. Design the API to support both patterns.

#### B.6 Tests

- **`test_sensorplacer/test_placement.py`**: Place devices in a simple 4-room building. Verify correct counts per type, all devices on walls, no device in excluded rooms, minimum spacing respected, deterministic.
- **`test_pathloss/test_intersection.py`**: Unit tests for ray-wall intersection. Include edge cases: ray parallel to wall, ray through door, ray through corner where two walls meet.
- **`test_pathloss/test_link_budget.py`**: Known-distance link with known wall materials. Verify FSPL formula, verify total path loss, verify rx_power calculation. Test both frequency bands.
- **`test_pathloss/test_graph.py`**: Build graph for small building. Verify symmetry (link A→B == B→A for path loss, NOT for rx_power if profiles differ). Verify all pairs present. Verify stochastic variation across different run_index values but determinism for same run_index.
- **`test_pathloss/test_materials.py`**: Load rf_materials.yaml. Verify all expected materials present with both frequency bands. Verify stochastic sampling produces values within 3σ (statistical test over many samples).

### Output Artifacts

| Artifact | Path |
|----------|------|
| Sensor placer | `buildingspacegen/sensorplacer/` |
| Path loss engine | `buildingspacegen/pathloss/` |
| RF material database | `data/materials/rf_materials.yaml` |
| Radio profiles | `data/radio_profiles/*.yaml` |
| Unit tests | `tests/test_sensorplacer/`, `tests/test_pathloss/` |

### Verification

Run `pytest tests/test_sensorplacer/ tests/test_pathloss/ -v`. All tests must pass. Then, using a hand-constructed simple Building object (a 2-room building with one interior wall), place devices and compute the path loss graph. Print the link results and verify the math by hand.

---

## Track C: 2D Visualizer

### Agent Instructions

You are building the interactive visualization layer. You consume the JSON interchange format (Preamble P.3) and render it as an interactive 2D top-down floor plan in the browser. You also provide a matplotlib renderer for quick Jupyter/terminal use.

**IMPORTANT**: You do NOT depend on Track A or B's Python code at runtime for the browser frontend. The frontend is a standalone HTML/JS application that consumes JSON from a FastAPI backend. The backend DOES import from `core/` to load and serve data.

### Scope

1. **`buildingspacegen/buildingviz/server/`** — FastAPI backend serving JSON
2. **`buildingspacegen/buildingviz/renderers/matplotlib_2d.py`** — matplotlib static renderer
3. **`buildingspacegen/buildingviz/frontend/`** — Browser-based interactive 2D visualizer
4. **`tests/test_buildingviz/`**

### Detailed Tasks

#### C.1 FastAPI Backend (`buildingviz/server/`)

Implement `app.py` with these endpoints:

```
GET  /api/building                → Full building JSON (P.3 schema, building section)
GET  /api/devices                 → Device list JSON (P.3 schema, devices + radio_profiles)
GET  /api/links?freq={hz}         → Link data for a frequency band (P.3 schema, links section)
GET  /api/scene                   → Complete scene JSON (full P.3 document)
POST /api/generate                → Generate a new building (params in body), return scene JSON
```

The server holds a "current scene" in memory. `POST /api/generate` calls the building generator pipeline (Track A → Track B) and replaces the current scene. If the pipeline isn't available yet, the server can load a scene from a pre-saved JSON file for frontend development.

**Implement a mock/fixture mode**: Ship a `data/fixtures/sample_scene.json` file containing a valid P.3 JSON document (hand-authored or generated). The server loads this on startup if no generator is available. This lets Track C develop the frontend independently.

#### C.2 matplotlib 2D Renderer (`buildingviz/renderers/matplotlib_2d.py`)

```python
def render_building_2d(
    building: Building,
    devices: Optional[DevicePlacement] = None,
    links: Optional[PathLossGraph] = None,
    frequency_hz: Optional[float] = None,
    figsize: tuple[float, float] = (16, 12),
    show_room_labels: bool = True,
    show_device_labels: bool = False,
    link_color_range: tuple[float, float] = (-100, -40),  # dBm range for colormap
    save_path: Optional[str] = None,
) -> matplotlib.figure.Figure:
```

Render:
- Room polygons filled with light colors by room type (use a consistent color palette)
- Walls as thick lines, color-coded by material (dark gray for concrete, light gray for gypsum, blue for glass, brown for wood)
- Doors as gaps in walls (or thin colored markers)
- Device positions as markers differentiated by type (circle for sensor, square for controller, diamond for main controller)
- If links provided: lines between device pairs, color-coded by rx_power (green → yellow → red gradient), with alpha proportional to link viability
- Room labels (room type + area) centered in each room
- Legend for room types, device types, and link color scale

This renderer is for quick development feedback and Jupyter notebooks. It does NOT need interactivity.

#### C.3 Browser Frontend (`buildingviz/frontend/`)

Build a single-page application in vanilla JS (no framework) with an HTML5 Canvas renderer.

**`index.html`**: Single page that loads `main.js`. Includes a control panel sidebar.

**`src/main.js`**: Entry point. Fetches `/api/scene` on load. Initializes canvas and all modules.

**`src/floorplan.js`**: Renders the building floor plan on canvas.
- Draw room polygons filled with room-type colors
- Draw walls with thickness proportional to material (gypsum thin, concrete thick)
- Draw doors as gaps
- Label rooms with type and area

**`src/devices.js`**: Renders device icons.
- Different shapes per device type (as defined above)
- Size indicates device importance (main controller largest)
- Position at (x, y) from device data

**`src/links.js`**: Renders connections between devices.
- Lines between paired devices
- Color mapped from rx_power: green (strong) → yellow → red (weak) → absent (below sensitivity)
- Line width optionally proportional to link margin
- Only render viable links by default (toggle to show all)

**`src/interaction.js`**: Pan, zoom, and hover.
- Mouse wheel zoom (centered on cursor)
- Click-drag pan
- Mouseover device: show tooltip with device_id, device_type, radio_profile name, room_id, position
- Mouseover link: show tooltip with tx/rx device ids, distance, path_loss, rx_power, walls_crossed, link_viable
- Click device: highlight all links from/to that device

**`src/filters.js`**: UI controls in the sidebar.
- Signal strength range slider: filter links by rx_power range
- Device type checkboxes: show/hide each device type
- Link visibility toggle: show all vs. viable only
- Frequency band selector: switch between 900 MHz and 2.4 GHz link data (re-fetches from `/api/links?freq=...`)
- Room type highlight: click a room type in the legend to highlight all rooms of that type

**`src/colormap.js`**: Shared color utilities.
- `rxPowerToColor(dbm, minDbm, maxDbm)` → CSS color string
- `roomTypeToColor(roomType)` → CSS color string
- `deviceTypeToShape(deviceType)` → shape descriptor
- `materialToColor(materialName)` → CSS color string

#### C.4 Phase 2 Readiness

Structure the frontend so that `floorplan.js` and `devices.js` are the only modules that reference Canvas 2D context. `interaction.js`, `filters.js`, and `colormap.js` work with abstract coordinates and data, not rendering primitives. When Three.js replaces Canvas in Phase 2, only `floorplan.js` and `devices.js` need to be swapped for `scene.js` and `building3d.js` — the interaction and filter logic transfers.

Document this separation in code comments at the top of each module.

#### C.5 Fixture Data

Create `data/fixtures/sample_scene.json` — a complete valid P.3 JSON document representing a small medium office (~5,000 sqft, ~8 rooms, ~15 devices, ~50 links). Hand-author or script this. It must be valid JSON conforming exactly to P.3.

#### C.6 Tests

- **`test_buildingviz/test_server.py`**: Use FastAPI TestClient. Test all endpoints return valid JSON. Test `/api/generate` with mock generator.
- **`test_buildingviz/test_matplotlib.py`**: Generate a figure from sample data. Verify it's a valid matplotlib Figure. Optionally save to PNG and check file exists.
- Manual verification: Start the server (`uvicorn buildingspacegen.buildingviz.server.app:app`), open browser, verify the floor plan renders with devices and links.

### Output Artifacts

| Artifact | Path |
|----------|------|
| FastAPI backend | `buildingspacegen/buildingviz/server/` |
| matplotlib renderer | `buildingspacegen/buildingviz/renderers/matplotlib_2d.py` |
| Browser frontend | `buildingspacegen/buildingviz/frontend/` |
| Fixture data | `data/fixtures/sample_scene.json` |
| Unit tests | `tests/test_buildingviz/` |

### Verification

1. Run `pytest tests/test_buildingviz/ -v` — all tests pass.
2. Start the FastAPI server with fixture data. Open browser to `http://localhost:8000`. Verify the floor plan renders with rooms, walls, devices, and links. Verify mouseover tooltips work. Verify filter controls work.

---

## Track D: Integration, CLI, and Batch Runner

### Agent Instructions

You are building the integration layer that ties Tracks A, B, and C together into a usable tool. You implement the CLI, the end-to-end pipeline, the batch Monte Carlo runner, and the integration tests that verify everything works together.

**IMPORTANT**: You depend on Tracks A, B, and C. Your code imports from all three. However, you can develop your CLI argument parsing, pipeline orchestration, and batch runner structure immediately — stub the actual calls to Track A and B APIs with TODO comments that reference the expected function signatures. Once Tracks A and B deliver, you fill in the stubs.

### Scope

1. **`buildingspacegen/cli/`** — CLI tool
2. **`buildingspacegen/pipeline.py`** — End-to-end orchestration
3. **Integration tests** — Full pipeline tests
4. **`pyproject.toml`** — Package configuration (coordinate with Track A)
5. **`examples/quickstart.py`** — Usage example

### Detailed Tasks

#### D.1 Pipeline Orchestration (`pipeline.py`)

```python
@dataclass
class PipelineConfig:
    building_type: BuildingType
    total_sqft: float
    num_floors: int = 1
    seed: int = 42
    generator: str = "bsp"
    placement_rules: Optional[PlacementRules] = None  # None → defaults
    radio_profiles: Optional[dict[DeviceType, RadioProfile]] = None
    frequencies_hz: list[float] = field(default_factory=lambda: [900e6, 2.4e9])
    archetype_overrides: Optional[dict] = None

@dataclass
class PipelineResult:
    building: Building
    placement: DevicePlacement
    path_loss_graphs: dict[float, PathLossGraph]  # freq → graph
    config: PipelineConfig

    def to_json(self) -> dict:
        """Serialize to P.3 JSON schema."""

    def save_json(self, path: str): ...

def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """
    Execute the full generation pipeline:
    1. Generate building (Track A)
    2. Place devices (Track B)
    3. Compute path loss graphs for each frequency (Track B)
    4. Return bundled result
    """
```

#### D.2 Batch Monte Carlo Runner

```python
@dataclass
class BatchConfig:
    base_config: PipelineConfig        # Base building config
    num_runs: int = 100                # Number of Monte Carlo runs
    seed_start: int = 0                # First building seed
    output_dir: str = "output/batch"
    save_individual: bool = False      # Save each run's JSON?
    parallel: bool = False             # Future: multiprocessing

@dataclass
class BatchSummary:
    num_runs: int
    building_type: str
    total_sqft: float
    frequencies_hz: list[float]
    per_frequency: dict[float, FrequencyBandSummary]

@dataclass
class FrequencyBandSummary:
    frequency_hz: float
    total_device_pairs: int
    viable_link_fraction: StatSummary      # mean, std, min, max across runs
    mean_path_loss_db: StatSummary
    mean_rx_power_dbm: StatSummary
    mean_walls_crossed: StatSummary
    isolated_device_fraction: StatSummary  # Devices with 0 viable links
    network_connectivity: StatSummary      # Fraction of devices in largest connected component

@dataclass
class StatSummary:
    mean: float
    std: float
    min: float
    max: float
    p5: float                              # 5th percentile
    p25: float
    p50: float                             # median
    p75: float
    p95: float

def run_batch(config: BatchConfig) -> BatchSummary:
    """
    Run Monte Carlo batch:
    1. For each run i in [0, num_runs):
       a. Set building seed = seed_start + i (different building each run)
       b. Run pipeline
       c. Extract summary statistics from path loss graph
       d. Optionally save individual JSON
    2. Aggregate statistics across all runs
    3. Return BatchSummary
    """
```

**Key design point**: Each Monte Carlo run generates a DIFFERENT building (different seed → different layout). The stochastic wall attenuation varies per run via `run_index`. This gives variance from both building layout AND material uncertainty. If the user wants to hold the building fixed and vary only attenuation, they can use the same building seed with different `run_index` values — expose this as a CLI option.

#### D.3 CLI (`cli/`)

Implement using `argparse` (or `click` if preferred). Register as `buildingspacegen` entry point in pyproject.toml.

```bash
# Generate a single building and save JSON
buildingspacegen generate \
  --type medium_office \
  --sqft 25000 \
  --seed 42 \
  --freq 900e6 2.4e9 \
  --radio-profile gen1_sensor \
  --output output/building.json

# Generate and visualize (open browser)
buildingspacegen visualize \
  --type medium_office \
  --sqft 25000 \
  --seed 42 \
  --port 8000

# Generate and render to PNG (matplotlib)
buildingspacegen render \
  --type medium_office \
  --sqft 25000 \
  --seed 42 \
  --freq 900e6 \
  --output output/floorplan.png

# Run Monte Carlo batch
buildingspacegen batch \
  --type medium_office \
  --sqft 25000 \
  --runs 100 \
  --seed-start 0 \
  --freq 900e6 2.4e9 \
  --output output/batch_results.json \
  --save-individual   # Optional: save each run's JSON

# Load and visualize an existing JSON file
buildingspacegen view \
  --input output/building.json \
  --port 8000
```

#### D.4 pyproject.toml

```toml
[project]
name = "buildingspacegen"
version = "0.1.0"
description = "Procedural building generator for wireless sensor network simulation"
requires-python = ">=3.10"
dependencies = [
    "numpy>=1.24",
    "shapely>=2.0",
    "networkx>=3.0",
    "pyyaml>=6.0",
    "matplotlib>=3.7",
    "fastapi>=0.100",
    "uvicorn>=0.22",
]

[project.optional-dependencies]
ifc = ["ifcopenshell>=0.7"]
dev = ["pytest>=7.0", "httpx>=0.24"]  # httpx for FastAPI TestClient

[project.scripts]
buildingspacegen = "buildingspacegen.cli.main:main"
```

#### D.5 Integration Tests (`tests/test_integration/`)

- **`test_pipeline.py`**: Run full pipeline for each building type. Verify output JSON conforms to P.3. Verify device count matches expected from placement rules. Verify path loss graph has correct number of edges.
- **`test_batch.py`**: Run batch with 5 runs. Verify BatchSummary statistics are populated. Verify different seeds produce different buildings. Verify same seed + same run_index produces identical results.
- **`test_cli.py`**: Invoke CLI commands via `subprocess.run`. Verify `generate` produces valid JSON file. Verify `batch` produces summary JSON.
- **`test_reproducibility.py`**: Generate building with seed X, serialize to JSON, deserialize, re-serialize. JSON must be byte-identical. Generate building twice with same params — must produce identical results.

#### D.6 Examples

`examples/quickstart.py`:

```python
"""Quick demonstration of the building space generator."""
from buildingspacegen.pipeline import run_pipeline, PipelineConfig
from buildingspacegen.core.enums import BuildingType

# Generate a medium office
config = PipelineConfig(
    building_type=BuildingType.MEDIUM_OFFICE,
    total_sqft=25000,
    seed=42,
)
result = run_pipeline(config)

# Print summary
print(f"Building: {result.building.building_type.value}")
print(f"Rooms: {sum(1 for _ in result.building.all_rooms())}")
print(f"Devices: {len(result.placement.devices)}")
for freq, graph in result.path_loss_graphs.items():
    viable = len(graph.get_viable_links(freq))
    total = len(graph.all_links)
    print(f"Links @ {freq/1e6:.0f} MHz: {viable}/{total} viable")

# Save JSON
result.save_json("output/demo_building.json")
print("Saved to output/demo_building.json")
```

### Output Artifacts

| Artifact | Path |
|----------|------|
| Pipeline orchestration | `buildingspacegen/pipeline.py` |
| CLI tool | `buildingspacegen/cli/` |
| pyproject.toml | `pyproject.toml` |
| Integration tests | `tests/test_integration/` |
| Examples | `examples/quickstart.py` |

### Verification

1. Run `pytest tests/test_integration/ -v` — all tests pass.
2. Execute `buildingspacegen generate --type medium_office --sqft 25000 --seed 42 --output /tmp/test.json` — produces valid JSON.
3. Execute `buildingspacegen batch --type medium_office --sqft 25000 --runs 5 --output /tmp/batch.json` — produces summary.
4. Run `examples/quickstart.py` — produces output without errors.

---

## Appendix: Dependency Graph Between Tracks

```
Track A (Core + Generator)
    │
    ├─── core/model.py, core/enums.py, core/geometry.py ──► Track B (consumes Building)
    │                                                       Track C (consumes JSON)
    │                                                       Track D (consumes all)
    │
    ├─── core/device.py ◄── Track B (implements placement)
    │                    ──► Track C (renders devices)
    │                    ──► Track D (orchestrates)
    │
    ├─── core/links.py  ◄── Track B (implements path loss)
    │                    ──► Track C (renders links)
    │                    ──► Track D (orchestrates)
    │
    └─── core/serialization.py ──► Track C (JSON API)
                                ──► Track D (JSON export)

Track B (Placer + Path Loss)
    │
    ├─── DevicePlacement ──► Track C, Track D
    └─── PathLossGraph   ──► Track C, Track D

Track C (Visualizer)
    │
    └─── FastAPI server  ◄── Track D (launches for visualize/view commands)

Track D (Integration)
    │
    └─── Depends on A, B, C — but can scaffold immediately
```

## Appendix: Parallelism and Sync Points

| Day | Track A | Track B | Track C | Track D |
|-----|---------|---------|---------|---------|
| 0 | Implement `core/` (ALL tracks block on this) | Start `rf_materials.yaml`, `radio_profiles/`, placer algorithm design | Start fixture JSON, FastAPI scaffold, frontend scaffold | Start pyproject.toml, CLI argument parsing, pipeline skeleton |
| 1 | BSP generator, archetypes | Placer implementation, path loss model | matplotlib renderer, frontend floorplan + devices | Pipeline orchestration, batch runner structure |
| 2 | Post-processing, validation, tests | Graph builder, dual-band, tests | Links rendering, interaction, filters | Integration with A + B, integration tests |
| 3 | Polish, edge cases | Polish, edge cases | Polish, tooltips, Phase 2 readiness | End-to-end tests, examples, CLI polish |

**Critical path**: Track A's `core/` is the day-0 deliverable. All other tracks can proceed with the interface definitions from this document, but integration requires the actual `core/` implementation. Track D integration-tests are the final gate.
