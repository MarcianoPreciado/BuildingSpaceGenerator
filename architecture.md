# System Architecture: Building Space Generator & Wireless Sensor Network Simulator

## 0. Approved Scope (Phase 1)

The following decisions were approved by the master architect on 2026-04-05:

- **Building types:** Medium office, large office, warehouse (priority order)
- **Frequency bands:** Dual-band support — 2.4 GHz and 900 MHz (Sub-GHz)
- **Floor scope:** Single-floor only for Phase 1 (multi-floor deferred)
- **Visualizer:** Phase 1 uses 2D top-down matplotlib/browser view with interactivity, architected for future Three.js 3D upgrade
- **Device taxonomy:** Three device types — Main Controller (low density/sqft, gravitates center), Secondary Controller (higher density/sqft), Sensor (min per-room AND min per-sqft)
- **Material attenuation:** Frequency-dependent values; stochastic sampling via normal distribution (μ = midpoint, 3σ = range bounds) per Monte Carlo run
- **Radio hardware:** Configurable per-device-generation hardware profiles (TX/RX gain, base frequency gain, etc.) to enable head-to-head protocol comparison across hardware revisions

## 1. Platform Overview

The full platform consists of five major subsystems that compose into two primary workflows: **batch Monte Carlo simulation** and **interactive single-building visualization**. The building generator is the foundational subsystem that feeds all others.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SIMULATION PLATFORM                              │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │   Building    │──▶│   Sensor     │──▶│   Path Loss / RF       │  │
│  │   Generator   │   │   Placer     │   │   Propagation Engine   │  │
│  └──────────────┘   └──────────────┘   └────────────────────────┘  │
│         │                                         │                 │
│         │                                         ▼                 │
│         │                              ┌────────────────────────┐  │
│         │                              │   Monte Carlo /        │  │
│         │                              │   Protocol Simulator   │  │
│         │                              └────────────────────────┘  │
│         │                                         │                 │
│         ▼                                         ▼                 │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  3D Visualizer / Dashboard                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Subsystem Breakdown

### 2.1 Building Generator (`buildinggen`)

**Purpose:** Given parameters (building type, square footage, seed), produce a complete building model with rooms, walls, materials, doors, and metadata.

**Architecture:**

```
buildinggen/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── model.py            # Core data model (Building, Floor, Room, Wall, Door, Material)
│   ├── enums.py            # BuildingType, RoomType, WallMaterial, etc.
│   └── geometry.py         # 2D/3D geometry primitives (Point, LineSegment, Polygon, BBox)
├── archetypes/
│   ├── __init__.py
│   ├── archetype.py        # BuildingArchetype base class
│   ├── registry.py         # Archetype registry (lookup by BuildingType)
│   ├── commercial_office.py
│   ├── warehouse.py
│   ├── retail.py
│   ├── industrial.py
│   ├── hospital.py
│   └── data/               # Parsed DOE reference building stats (JSON/YAML)
│       ├── medium_office.yaml
│       ├── large_office.yaml
│       ├── warehouse.yaml
│       └── ...
├── generators/
│   ├── __init__.py
│   ├── base.py             # Abstract generator interface
│   ├── bsp.py              # Binary Space Partitioning generator
│   ├── treemap.py          # Squarified Treemap generator
│   └── genetic.py          # Genetic/evolutionary layout (for industrial)
├── postprocess/
│   ├── __init__.py
│   ├── corridors.py        # Add corridors and circulation paths
│   ├── doors.py            # Place doors between adjacent rooms
│   ├── materials.py        # Assign wall materials based on room types
│   └── validation.py       # Validate building model (connectivity, min sizes, etc.)
├── exporters/
│   ├── __init__.py
│   ├── ifc.py              # Export to IFC via IfcOpenShell
│   ├── json_export.py      # Export to JSON (for visualizer)
│   ├── obj_export.py       # Export to OBJ/STL (for 3D tools)
│   └── energyplus.py       # Export to EnergyPlus IDF (future)
└── api.py                  # High-level public API
```

**Core Data Model:**

```python
@dataclass
class Material:
    name: str                    # e.g., "concrete_block", "gypsum_board"
    thickness_m: float           # meters
    rf_attenuation_db: float     # dB loss at reference frequency
    # Optional thermal/acoustic properties for future use

@dataclass
class WallSegment:
    start: Point2D
    end: Point2D
    height: float
    materials: list[Material]    # Ordered outside-to-inside
    is_exterior: bool

@dataclass
class Door:
    wall: WallSegment
    position_along_wall: float   # 0.0 to 1.0
    width: float
    height: float

@dataclass
class Room:
    id: str
    room_type: RoomType          # OPEN_OFFICE, CONFERENCE, MECHANICAL, etc.
    polygon: Polygon2D           # Floor boundary
    floor_index: int
    walls: list[WallSegment]
    doors: list[Door]
    ceiling_height: float
    area_sqft: float             # Computed from polygon

@dataclass
class Floor:
    index: int
    rooms: list[Room]
    elevation: float             # Height above ground
    footprint: Polygon2D         # Outer boundary

@dataclass
class Building:
    building_type: BuildingType
    floors: list[Floor]
    footprint: Polygon2D
    total_area_sqft: float
    seed: int                    # For reproducibility
    metadata: dict               # Arbitrary additional data

    def all_rooms(self) -> Iterator[Room]: ...
    def all_walls(self) -> Iterator[WallSegment]: ...
    def get_wall_between(self, room_a: Room, room_b: Room) -> Optional[WallSegment]: ...
```

**Public API:**

```python
from buildinggen import generate_building, BuildingType

building = generate_building(
    building_type=BuildingType.LARGE_OFFICE,
    total_sqft=50000,
    num_floors=3,
    seed=42,
    # Optional overrides:
    generator="bsp",                    # or "treemap", "genetic"
    exterior_wall_material="concrete",
    interior_wall_material="gypsum",
)

# Access the model
for floor in building.floors:
    for room in floor.rooms:
        print(f"{room.room_type}: {room.area_sqft} sqft")

# Export
building.export_json("output/building.json")
building.export_ifc("output/building.ifc")
```

**Generation Pipeline:**

```
Input Parameters
      │
      ▼
┌─────────────────┐
│ Archetype Lookup │  ← Uses DOE reference data to determine
│                  │    room-type distributions, typical sizes,
│                  │    wall constructions for this building type
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Footprint Gen   │  ← Generate building footprint polygon
│                  │    (rectangular, L-shape, U-shape, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Space Partition  │  ← BSP/Treemap/Genetic subdivides footprint
│ (per floor)      │    into rooms matching archetype distribution
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Room Assignment  │  ← Assign room types to partitions based on
│                  │    size, adjacency rules, archetype weights
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Post-Processing  │  ← Add corridors, doors, assign materials,
│                  │    validate connectivity and constraints
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Building Model   │  ← Complete Building object ready for use
└─────────────────┘
```

---

### 2.2 Sensor Placer (`sensorplacer`)

**Purpose:** Given a Building and placement rules, position sensors and controllers on walls throughout the building.

```
sensorplacer/
├── __init__.py
├── model.py          # Device, MainController, SecondaryController, Sensor, DevicePlacement
├── rules.py          # Placement rule definitions per device type
├── placer.py         # Rule-based placement engine
├── optimizer.py      # Optional optimization-based placement
└── api.py            # High-level API
```

**Device Taxonomy (Three Types):**

```python
class DeviceType(Enum):
    MAIN_CONTROLLER = "main_controller"
    SECONDARY_CONTROLLER = "secondary_controller"
    SENSOR = "sensor"

@dataclass
class PlacementRules:
    """Configurable placement rules for each device type."""

    # Main Controllers: low density, gravitate toward building center
    main_controller_per_sqft: float       # e.g., 1 per 25,000 sqft
    main_controller_wall_height_m: float  # e.g., 2.0m
    main_controller_prefer_center: bool   # When count=1, place near centroid

    # Secondary Controllers: higher density than main
    secondary_controller_per_sqft: float  # e.g., 1 per 5,000 sqft
    secondary_controller_wall_height_m: float

    # Sensors: min per-room AND min per-sqft (whichever yields more)
    sensor_min_per_room: int              # e.g., 1 (every room gets at least 1)
    sensor_per_sqft: float                # e.g., 1 per 500 sqft
    sensor_wall_height_m: float           # e.g., 1.5m
    sensor_min_spacing_m: float           # Minimum distance between sensors on same wall

    # Excluded room types (e.g., no sensors in mechanical closets)
    excluded_room_types: list[RoomType]
```

**Placement Algorithm:**
1. **Main Controllers first:** Compute count from building total sqft. If count=1, find the wall position closest to building centroid. If count>1, distribute evenly using k-means on building area, then snap each to nearest wall.
2. **Secondary Controllers next:** Compute count from sqft density. Distribute to maximize coverage gaps between main controllers. Place on walls.
3. **Sensors last:** For each room, compute `max(min_per_room, ceil(room_sqft / sensor_per_sqft))`. Distribute sensors evenly along room walls at configured height, respecting min_spacing.

**Wall-Mounting:** All devices are placed at specific (x, y, z) positions on wall surfaces. The z-coordinate is the configured wall height. The (x, y) position is a point along a wall segment. The placer distributes positions evenly along available wall length.

**Output:** A `DevicePlacement` containing a list of `Device` objects, each with a position, device type, the room it's in, the wall it's mounted on, and a reference to its `RadioProfile`.

---

### 2.3 Path Loss Engine (`pathloss`)

**Purpose:** Given a Building, two positions, a frequency band, and radio hardware profiles, compute the RF path loss / received signal strength between them.

```
pathloss/
├── __init__.py
├── models/
│   ├── base.py              # Abstract PathLossModel interface
│   ├── multiwall.py         # ITU-R P.1238 / Motley-Keenan multi-wall model
│   ├── logdistance.py       # Log-distance / free-space path loss (FSPL baseline)
│   └── ray_tracing.py       # PyLayers integration (optional, high-fidelity)
├── materials.py             # RF material attenuation database (frequency-dependent, stochastic)
├── radio.py                 # RadioProfile: TX/RX gain, antenna characteristics, frequency config
├── geometry.py              # Ray-wall intersection algorithms
├── graph.py                 # Build complete path-loss graph between all device pairs
└── api.py
```

**Dual-Band Frequency Support:**
The engine supports both 2.4 GHz and 900 MHz bands. Every computation takes `frequency_hz` as a parameter. Material attenuation, free-space path loss, and antenna gains all vary with frequency.

**Stochastic Material Attenuation (Monte Carlo):**
Wall attenuation is not a fixed value — it's sampled per-wall per-simulation-run from a normal distribution. For each material at each frequency band, the database stores `(mean_db, sigma_db)` where `sigma = (upper_bound - lower_bound) / 6` (3-sigma range covers the published bounds). Each Monte Carlo run seeds the RNG and samples attenuation values, producing realistic variance across simulation runs.

```python
@dataclass
class MaterialRFProperties:
    """RF attenuation properties for a single material at a specific frequency."""
    frequency_hz: float
    mean_attenuation_db: float     # μ (midpoint of published range)
    sigma_attenuation_db: float    # σ (range / 6 for 3-sigma coverage)

    def sample(self, rng: np.random.Generator) -> float:
        """Sample an attenuation value for this Monte Carlo run."""
        return max(0.0, rng.normal(self.mean_attenuation_db, self.sigma_attenuation_db))

@dataclass
class MaterialRFDatabase:
    """Frequency-dependent RF attenuation properties for all materials."""
    # Keyed by (material_name, frequency_hz)
    entries: dict[tuple[str, float], MaterialRFProperties]

    def get_attenuation(self, material: str, frequency_hz: float, rng: np.random.Generator) -> float:
        props = self.entries[(material, frequency_hz)]
        return props.sample(rng)
```

**Radio Hardware Profiles:**
To compare hardware generations head-to-head, each device references a `RadioProfile` that captures the RF hardware characteristics. This is configured per-simulation, not per-building.

```python
@dataclass
class RadioProfile:
    """Hardware-specific radio parameters for a device generation."""
    name: str                       # e.g., "gen1_sensor", "gen2_sensor"
    tx_power_dbm: float             # Transmit power
    tx_antenna_gain_dbi: float      # Transmit antenna gain
    rx_antenna_gain_dbi: float      # Receive antenna gain
    rx_sensitivity_dbm: float       # Minimum receivable signal
    frequency_hz: float             # Operating frequency (900e6 or 2.4e9)
    # Future: noise figure, bandwidth, modulation parameters
```

**Core Link Budget Computation:**
```python
def compute_link(tx_pos, rx_pos, building, tx_profile, rx_profile, material_db, rng):
    distance_m = euclidean_distance(tx_pos, rx_pos)
    freq_hz = tx_profile.frequency_hz  # TX and RX must be on same band

    # Free-space path loss (Friis)
    fspl_db = 20*log10(distance_m) + 20*log10(freq_hz) - 147.55

    # Stochastic multi-wall attenuation
    intersected_walls = find_wall_intersections(tx_pos, rx_pos, building)
    wall_loss_db = sum(
        material_db.get_attenuation(wall.material_name, freq_hz, rng)
        for wall in intersected_walls
    )

    # Total path loss
    path_loss_db = fspl_db + wall_loss_db

    # Received signal strength
    rx_power_dbm = (tx_profile.tx_power_dbm
                    + tx_profile.tx_antenna_gain_dbi
                    + rx_profile.rx_antenna_gain_dbi
                    - path_loss_db)

    # Can the receiver hear this?
    link_viable = rx_power_dbm >= rx_profile.rx_sensitivity_dbm

    return LinkResult(
        path_loss_db=path_loss_db,
        rx_power_dbm=rx_power_dbm,
        distance_m=distance_m,
        walls_crossed=len(intersected_walls),
        wall_loss_db=wall_loss_db,
        fspl_db=fspl_db,
        link_viable=link_viable,
    )
```

**Graph Construction:** For N devices, compute the N×(N-1)/2 pairwise link results. Store as a weighted graph (NetworkX) where edge attributes include path loss, received power, wall count, and viability. This graph is the primary input to the protocol simulator.

---

### 2.4 Protocol Simulator (`protosim`) — Future Subsystem

**Purpose:** Given the path-loss graph and device list, simulate the wireless mesh protocol over time (1 year), modeling solar power, adaptive sample rates, connection intervals, and routing.

This subsystem is out of scope for the building generator project but is the primary consumer. The interface contract is:

```python
# What protosim needs from us:
path_loss_graph: nx.Graph        # Nodes = devices, edges = path loss (dB)
device_list: list[Device]        # Each device has position, room, type
building_metadata: dict          # Building type, floor count, etc.
```

---

### 2.5 Visualizer (`buildingviz`)

**Purpose:** Interactive visualization of a building floor plan with sensor network overlay.

**Phase 1 Architecture:** 2D top-down view using matplotlib (desktop/Jupyter) and/or a lightweight browser canvas (Plotly Dash or plain HTML+JS). Architected so the data layer and JSON schema are reusable when upgrading to Three.js 3D in Phase 2.

```
buildingviz/
├── __init__.py
├── server/
│   ├── __init__.py
│   ├── app.py               # FastAPI application
│   ├── routes/
│   │   ├── building.py      # GET /api/building/{id} → floor plan geometry JSON
│   │   ├── devices.py       # GET /api/devices/{id} → sensor positions + data
│   │   ├── links.py         # GET /api/links/{id} → connection data with path loss
│   │   └── simulation.py    # GET /api/simulation/{id} → simulation results
│   └── services/
│       ├── building_service.py
│       └── simulation_service.py
├── renderers/
│   ├── __init__.py
│   ├── base.py              # Abstract renderer interface (2D and future 3D share this)
│   ├── matplotlib_2d.py     # matplotlib top-down floor plan renderer (quick dev use)
│   └── web_2d.py            # Browser-based 2D renderer (Plotly Dash or HTML canvas)
├── frontend/                # Phase 1: 2D canvas; Phase 2: Three.js upgrade
│   ├── index.html
│   ├── src/
│   │   ├── main.js          # Entry point
│   │   ├── floorplan.js     # 2D floor plan rendering (walls, rooms as polygons)
│   │   ├── devices.js       # Device icons at (x, y) positions
│   │   ├── links.js         # Connection lines between devices (color-coded)
│   │   ├── interaction.js   # Mouseover, click, tooltips (works in 2D and future 3D)
│   │   ├── filters.js       # Signal strength filters, device state filters
│   │   └── colormap.js      # Color mapping utilities
│   └── assets/
│       └── icons/            # SVG icons for sensors, controllers
└── README.md
```

**Phase 1 Visualization Features (2D top-down):**
- Pan and zoom on a 2D floor plan view
- Rooms drawn as filled polygons with labels (room type, area)
- Walls drawn with thickness/color indicating material type
- Device icons at wall positions, differentiated by type (main controller, secondary controller, sensor)
- Color-coded connection lines between devices by signal strength (green → yellow → red → absent)
- Mouseover tooltips on connections: path loss, rx power, wall count
- Mouseover tooltips on devices: device type, radio profile, net power, sample rate, dependents
- Filter connections by signal strength range (slider)
- Colorize devices by: controller reachability (reachable/unreachable), net power income (gradient)

**Phase 2 Upgrade Path (Three.js 3D):**
The JSON API schema is designed to carry 3D coordinates (x, y, z) even though Phase 1 only renders x, y. When Three.js is added, the frontend swaps `floorplan.js` for a `scene.js` + `building.js` 3D renderer while reusing `interaction.js`, `filters.js`, `colormap.js`, and the entire backend API unchanged.

---

## 3. Cross-Cutting Concerns

### 3.1 Reproducibility
Every generated building must be fully reproducible from its parameters + seed. All random operations use `numpy.random.Generator` seeded from the building seed. No global random state.

### 3.2 Serialization
The internal Building model serializes to JSON for the visualizer and to IFC for standards compliance. The JSON schema is the canonical interchange format between subsystems.

### 3.3 Performance for Monte Carlo
The building generator must produce a building in < 1 second for batch simulation. The multi-wall path loss model must compute all pairwise losses for ~500 devices in < 5 seconds. The full pipeline (generate → place → compute graph) must complete in < 10 seconds per building.

### 3.4 Extensibility
- New building types: Add a new archetype YAML + optional generator tweaks.
- New room types: Add to the RoomType enum + material assignment rules.
- New path loss models: Implement the PathLossModel interface.
- New export formats: Implement the Exporter interface.
- New visualization layers: Add a new .js module in the frontend.

### 3.5 Dependencies (Minimal Core)

**Core (building generator + sensor placer + path loss):**
- Python 3.10+
- numpy
- shapely (2D geometry)
- networkx (graph construction)
- pyyaml (archetype data)

**Optional:**
- ifcopenshell (IFC export)
- scipy (optimization-based placement)
- matplotlib (quick debug plots)

**Visualizer:**
- fastapi + uvicorn (backend)
- three.js (frontend, CDN or bundled)

---

## 4. Data Flow Diagrams

### 4.1 Batch Monte Carlo Flow

```
for seed in range(N):
    building = generate_building(type, sqft, floors, seed)
    devices  = place_sensors(building, rules)
    graph    = compute_path_loss_graph(building, devices, model)
    score    = run_protocol_simulation(graph, devices, protocol_params)
    results.append(score)

analyze_results(results)  # Statistics, distributions, comparisons
```

### 4.2 Single Building Visualization Flow

```
building = generate_building(type, sqft, floors, seed)
devices  = place_sensors(building, rules)
graph    = compute_path_loss_graph(building, devices, model)
sim_data = run_protocol_simulation(graph, devices, protocol_params)

# Serve to visualizer
start_viz_server(building, devices, graph, sim_data)
# → Opens browser with interactive 3D view
```

---

## 5. Building Generator Algorithm Detail

### 5.1 Primary Algorithm: BSP with Archetype Constraints

**Step 1 — Footprint Generation:**
- Input: total_sqft, num_floors, building_type
- Per-floor sqft = total_sqft / num_floors
- Footprint aspect ratio sampled from archetype distribution (e.g., offices: 1.2-2.0, warehouses: 1.5-4.0)
- Footprint shape: rectangle (most common), or L/U/T for larger buildings (controlled by archetype)

**Step 2 — Room Program Generation:**
- From archetype, generate a "room program": a list of (room_type, target_area) tuples
- Example for medium office: 60% open office, 15% conference, 10% private office, 5% kitchen/break, 5% restroom, 5% mechanical/IT
- Room count and sizes sampled from archetype distributions with seeded RNG
- Total room area ≈ 85-90% of floor area (remainder becomes corridors)

**Step 3 — BSP Subdivision:**
```
function bsp_partition(rect, room_list, rng):
    if len(room_list) == 1:
        assign room_list[0] to rect
        return

    # Split room_list into two groups by total area
    split_ratio = sum(areas of group_A) / sum(all areas)

    # Choose split axis (alternate, or based on aspect ratio)
    if rect.width > rect.height:
        split vertically at split_ratio
    else:
        split horizontally at split_ratio

    # Add small random perturbation to split position (seeded)
    perturbation = rng.uniform(-0.05, 0.05) * dimension

    bsp_partition(left_rect, group_A, rng)
    bsp_partition(right_rect, group_B, rng)
```

**Step 4 — Corridor Insertion:**
- Identify the main circulation spine (longest axis of building)
- Insert corridor along spine (configurable width, typically 1.5-2m)
- For deep floor plates, add secondary corridors
- Re-partition rooms that were split by corridor insertion

**Step 5 — Post-Processing:**
- Assign wall materials: exterior walls get archetype exterior construction, interior walls get archetype interior construction, walls between certain room types get upgraded (e.g., server room → concrete)
- Place doors between adjacent rooms that share a wall
- Validate: all rooms accessible from corridor, minimum room sizes met, room types correctly distributed

### 5.2 Secondary Algorithm: Treemap (Simpler, Faster)

Squarified treemap algorithm treats the room program as a weighted list and fills the footprint rectangle with near-square subdivisions. Faster than BSP, produces slightly less realistic layouts but fully adequate for Monte Carlo batches. Good fallback.

### 5.3 Tertiary Algorithm: Genetic Layout (Industrial)

For warehouses and industrial buildings with strong adjacency requirements:
- Represent layout as a chromosome (room positions/sizes)
- Fitness function scores: adjacency satisfaction, traffic flow, structural feasibility
- Evolve population over generations
- Slower but produces more realistic industrial layouts

---

## 6. Wall Material RF Attenuation Database

Based on published research (ITU-R P.2040, various IEEE papers). Values are frequency-dependent — 900 MHz propagates better through most materials.

### 6.1 Attenuation Ranges (Published Bounds)

| Material | Thickness | 2.4 GHz Range | 2.4 GHz μ / σ | 900 MHz Range | 900 MHz μ / σ |
|----------|-----------|---------------|----------------|---------------|----------------|
| Gypsum/Drywall | 13mm | 2–4 dB | 3.0 / 0.33 | 1–3 dB | 2.0 / 0.33 |
| Gypsum double (partition) | 26mm+air | 4–7 dB | 5.5 / 0.50 | 3–5 dB | 4.0 / 0.33 |
| Concrete block | 200mm | 10–15 dB | 12.5 / 0.83 | 8–12 dB | 10.0 / 0.67 |
| Reinforced concrete | 200mm | 15–25 dB | 20.0 / 1.67 | 12–20 dB | 16.0 / 1.33 |
| Brick | 100mm | 6–10 dB | 8.0 / 0.67 | 4–8 dB | 6.0 / 0.67 |
| Glass (standard) | 6mm | 2–4 dB | 3.0 / 0.33 | 1–2 dB | 1.5 / 0.17 |
| Glass (low-E coated) | 6mm | 8–12 dB | 10.0 / 0.67 | 6–10 dB | 8.0 / 0.67 |
| Wood (interior door) | 45mm | 3–5 dB | 4.0 / 0.33 | 2–4 dB | 3.0 / 0.33 |
| Metal (fire door) | 50mm | 15–25 dB | 20.0 / 1.67 | 12–20 dB | 16.0 / 1.33 |
| Elevator shaft (steel) | — | 25–40 dB | 32.5 / 2.50 | 20–35 dB | 27.5 / 2.50 |

### 6.2 Stochastic Sampling Model

For Monte Carlo simulation, each wall's attenuation is sampled per-run (not per-ray):

```
σ = (upper_bound - lower_bound) / 6
μ = (upper_bound + lower_bound) / 2
attenuation = max(0, Normal(μ, σ))    # Clamped to non-negative
```

The 3-sigma rule ensures 99.7% of samples fall within the published bounds. The RNG is seeded per-simulation for reproducibility.

**Important:** Attenuation values are sampled once per wall per simulation run (not per link computation). This means a given wall has a fixed attenuation for a given Monte Carlo trial, but varies across trials. This reflects the reality that a specific wall has fixed-but-unknown properties, and our uncertainty about those properties drives the Monte Carlo variance.

### 6.3 Radio Hardware Profile Defaults

Example profiles for head-to-head comparison of hardware generations:

```yaml
# gen1_sensor.yaml
name: "Gen 1 Sensor"
tx_power_dbm: 0.0
tx_antenna_gain_dbi: 2.0
rx_antenna_gain_dbi: 2.0
rx_sensitivity_dbm: -95.0
supported_frequencies_hz: [900.0e6, 2400.0e6]

# gen2_sensor.yaml
name: "Gen 2 Sensor"
tx_power_dbm: 4.0
tx_antenna_gain_dbi: 3.0
rx_antenna_gain_dbi: 3.0
rx_sensitivity_dbm: -100.0
supported_frequencies_hz: [900.0e6, 2400.0e6]

# main_controller.yaml
name: "Main Controller"
tx_power_dbm: 10.0
tx_antenna_gain_dbi: 5.0
rx_antenna_gain_dbi: 5.0
rx_sensitivity_dbm: -105.0
supported_frequencies_hz: [900.0e6, 2400.0e6]
```

These profiles are passed into the path loss engine and protocol simulator to compute realistic link budgets per hardware generation.
