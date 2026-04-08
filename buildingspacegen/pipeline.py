"""
End-to-end pipeline: generate building → place devices → compute path loss graphs.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from buildingspacegen.core.enums import BuildingType, DeviceType
from buildingspacegen.core.model import Building
from buildingspacegen.core.device import DevicePlacement, PlacementRules, RadioProfile
from buildingspacegen.core.links import PathLossGraph


@dataclass
class PipelineConfig:
    building_type: BuildingType
    total_sqft: float
    num_floors: int = 1
    seed: int = 42
    generator: str = "bsp"
    placement_rules: Optional[PlacementRules] = None   # None → use DEFAULT_RULES
    radio_profiles: Optional[dict] = None              # None → load from data/radio_profiles/
    frequencies_hz: list = field(default_factory=lambda: [900e6, 2.4e9])
    archetype_overrides: Optional[dict] = None
    materials_yaml: Optional[str] = None               # None → auto-detect data/materials/rf_materials.yaml
    radio_profiles_dir: Optional[str] = None           # None → auto-detect data/radio_profiles/


@dataclass
class PipelineResult:
    building: Building
    placement: DevicePlacement
    path_loss_graphs: dict          # freq (float) → PathLossGraph
    config: PipelineConfig

    def annotate_sensor_connectivity(self) -> None:
        """Mark each sensor with controller-link viability across all available bands."""
        controller_ids = {
            device.id
            for device in self.placement.devices
            if device.device_type in {
                DeviceType.MAIN_CONTROLLER,
                DeviceType.SECONDARY_CONTROLLER,
            }
        }

        viable_frequencies_by_sensor: dict[str, set[float]] = {
            device.id: set()
            for device in self.placement.devices
            if device.device_type == DeviceType.SENSOR
        }

        for graph in self.path_loss_graphs.values():
            for link in graph.all_links:
                if not link.link_viable:
                    continue

                if link.tx_device_id in controller_ids and link.rx_device_id in viable_frequencies_by_sensor:
                    viable_frequencies_by_sensor[link.rx_device_id].add(link.frequency_hz)

                if link.rx_device_id in controller_ids and link.tx_device_id in viable_frequencies_by_sensor:
                    viable_frequencies_by_sensor[link.tx_device_id].add(link.frequency_hz)

        for device in self.placement.devices:
            if device.device_type != DeviceType.SENSOR:
                continue

            metadata = dict(device.metadata)
            viable_frequencies = sorted(viable_frequencies_by_sensor.get(device.id, set()))
            metadata["has_viable_controller_link"] = bool(viable_frequencies)
            metadata["viable_controller_link_frequencies_hz"] = viable_frequencies
            device.metadata = metadata

    def merged_links(self) -> PathLossGraph:
        """Combine all per-frequency graphs into a single graph."""
        merged = PathLossGraph()
        for graph in self.path_loss_graphs.values():
            for link in graph.all_links:
                merged.add_link(link)
        return merged

    def to_json(self) -> dict:
        """Serialize to P.3 JSON schema."""
        from buildingspacegen.core.serialization import serialize_building_scene
        self.annotate_sensor_connectivity()
        radio_profiles = {}
        for device in self.placement.devices:
            rp = device.radio_profile
            radio_profiles[rp.name] = rp
        return serialize_building_scene(
            building=self.building,
            devices=self.placement,
            links=self.merged_links(),
            radio_profiles=radio_profiles,
        )

    def save_json(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_json(), f, indent=2)


def _find_data_dir() -> str:
    """Find the data/ directory with materials subdirectory (for materials and radio profiles)."""
    here = os.path.dirname(os.path.abspath(__file__))
    # Try: ../data (parent of buildingspacegen), buildingspacegen/data, ./data, etc.
    candidates = [
        os.path.join(here, '..', 'data'),
        os.path.join(here, 'data'),
        os.path.join(os.getcwd(), 'data'),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isdir(os.path.join(c, 'materials')):
            return os.path.abspath(c)
    raise FileNotFoundError(f"Cannot find data/ directory with materials. Tried: {candidates}")


def _find_archetype_dir() -> str:
    """Find the archetypes/ directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    # Try: buildingspacegen/data/archetypes/, ../data/archetypes, etc.
    candidates = [
        os.path.join(here, 'data', 'archetypes'),
        os.path.join(here, '..', 'data', 'archetypes'),
        os.path.join(os.getcwd(), 'data', 'archetypes'),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.abspath(c)
    raise FileNotFoundError(f"Cannot find archetypes/ directory. Tried: {candidates}")


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """
    Execute the full generation pipeline:
    1. Generate building (Track A)
    2. Place devices (Track B)
    3. Compute path loss graphs for each frequency (Track B)
    4. Return bundled PipelineResult
    """
    from buildingspacegen.buildinggen.api import generate_building, load_archetype_directory
    from buildingspacegen.sensorplacer.api import place_sensors
    from buildingspacegen.pathloss.graph import build_path_loss_graphs
    from buildingspacegen.pathloss.materials import MaterialRFDatabase
    from buildingspacegen.pathloss.radio import RadioProfileRegistry
    from buildingspacegen.pathloss.models.multiwall import MultiWallPathLossModel
    from buildingspacegen.sensorplacer.rules import DEFAULT_RULES

    # Find and load archetypes
    archetype_dir = _find_archetype_dir()
    load_archetype_directory(archetype_dir)

    # 1. Generate building
    building = generate_building(
        building_type=config.building_type,
        total_sqft=config.total_sqft,
        num_floors=config.num_floors,
        seed=config.seed,
        generator=config.generator,
        archetype_overrides=config.archetype_overrides,
    )

    # 2. Load materials DB
    data_dir = _find_data_dir()
    materials_path = config.materials_yaml or os.path.join(data_dir, 'materials', 'rf_materials.yaml')
    material_db = MaterialRFDatabase.from_yaml(materials_path)

    # 3. Load radio profiles
    profiles_dir = config.radio_profiles_dir or os.path.join(data_dir, 'radio_profiles')
    registry = RadioProfileRegistry.from_directory(profiles_dir)

    # Build radio profiles dict for placer
    if config.radio_profiles is None:
        radio_profiles = {
            DeviceType.MAIN_CONTROLLER: registry.get('main_controller'),
            DeviceType.SECONDARY_CONTROLLER: registry.get('gen1_sensor'),
            DeviceType.SENSOR: registry.get('gen1_sensor'),
        }
    else:
        radio_profiles = config.radio_profiles

    # 4. Place devices
    rules = config.placement_rules or DEFAULT_RULES
    placement = place_sensors(
        building=building,
        rules=rules,
        radio_profiles=radio_profiles,
    )

    # 5. Compute path loss graphs for each frequency
    model = MultiWallPathLossModel(material_db)
    path_loss_graphs = build_path_loss_graphs(
        building=building,
        placement=placement,
        model=model,
        material_db=material_db,
        frequencies_hz=config.frequencies_hz,
        seed=config.seed,
    )

    result = PipelineResult(
        building=building,
        placement=placement,
        path_loss_graphs=path_loss_graphs,
        config=config,
    )
    result.annotate_sensor_connectivity()
    return result


# ============================================================================
# Batch Monte Carlo Runner
# ============================================================================

@dataclass
class StatSummary:
    mean: float
    std: float
    min: float
    max: float
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float

    @classmethod
    def from_array(cls, arr) -> 'StatSummary':
        arr = np.array(arr, dtype=float)
        if len(arr) == 0:
            return cls(0, 0, 0, 0, 0, 0, 0, 0, 0)
        return cls(
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            p5=float(np.percentile(arr, 5)),
            p25=float(np.percentile(arr, 25)),
            p50=float(np.percentile(arr, 50)),
            p75=float(np.percentile(arr, 75)),
            p95=float(np.percentile(arr, 95)),
        )


@dataclass
class FrequencyBandSummary:
    frequency_hz: float
    total_device_pairs: int
    viable_link_fraction: StatSummary
    mean_path_loss_db: StatSummary
    mean_rx_power_dbm: StatSummary
    mean_walls_crossed: StatSummary
    isolated_device_fraction: StatSummary
    network_connectivity: StatSummary


@dataclass
class BatchSummary:
    num_runs: int
    building_type: str
    total_sqft: float
    frequencies_hz: list
    per_frequency: dict   # freq → FrequencyBandSummary

    def to_dict(self) -> dict:
        import dataclasses
        def _convert(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            return obj
        return _convert(self)


@dataclass
class BatchConfig:
    base_config: PipelineConfig
    num_runs: int = 100
    seed_start: int = 0
    output_dir: str = "output/batch"
    save_individual: bool = False
    parallel: bool = False   # Future: multiprocessing


def _extract_graph_stats(graph, frequency_hz: float, num_devices: int) -> dict:
    """Extract summary statistics from a single PathLossGraph."""
    try:
        import networkx as nx
    except ImportError:
        nx = None

    all_links = graph.all_links
    viable_links = graph.get_viable_links(frequency_hz)

    total_pairs = num_devices * (num_devices - 1)  # directed pairs
    viable_frac = len(viable_links) / total_pairs if total_pairs > 0 else 0

    path_losses = [l.path_loss_db for l in all_links if l.frequency_hz == frequency_hz]
    rx_powers = [l.rx_power_dbm for l in all_links if l.frequency_hz == frequency_hz]
    walls = [l.walls_crossed for l in all_links if l.frequency_hz == frequency_hz]

    # Isolated devices: 0 viable links
    device_ids = set()
    for l in all_links:
        device_ids.add(l.tx_device_id)
        device_ids.add(l.rx_device_id)
    connected = set()
    for l in viable_links:
        connected.add(l.tx_device_id)
        connected.add(l.rx_device_id)
    isolated_frac = 1 - (len(connected) / len(device_ids)) if device_ids else 0

    # Network connectivity: fraction of devices in largest connected component
    connectivity = 0.0
    if nx is not None:
        G = graph.to_networkx(frequency_hz)
        if G.number_of_nodes() > 0:
            try:
                components = list(nx.connected_components(G.to_undirected() if G.is_directed() else G))
                largest = max(components, key=len) if components else set()
                connectivity = len(largest) / G.number_of_nodes()
            except (AttributeError, TypeError):
                connectivity = 0.0

    return {
        'viable_frac': viable_frac,
        'path_losses': path_losses,
        'rx_powers': rx_powers,
        'walls': walls,
        'isolated_frac': isolated_frac,
        'connectivity': connectivity,
        'total_pairs': total_pairs,
    }


def run_batch(config: BatchConfig) -> BatchSummary:
    """
    Run Monte Carlo batch simulation.
    Each run uses a different building seed → different building layout.
    Wall attenuation varies per run via run_index.
    """
    import os

    base = config.base_config
    all_stats = {freq: {
        'viable_fracs': [],
        'path_losses': [],
        'rx_powers': [],
        'walls': [],
        'isolated_fracs': [],
        'connectivities': [],
        'total_pairs': 0,
    } for freq in base.frequencies_hz}

    os.makedirs(config.output_dir, exist_ok=True)

    for i in range(config.num_runs):
        run_config = PipelineConfig(
            building_type=base.building_type,
            total_sqft=base.total_sqft,
            num_floors=base.num_floors,
            seed=config.seed_start + i,
            generator=base.generator,
            placement_rules=base.placement_rules,
            radio_profiles=base.radio_profiles,
            frequencies_hz=base.frequencies_hz,
            archetype_overrides=base.archetype_overrides,
            materials_yaml=base.materials_yaml,
            radio_profiles_dir=base.radio_profiles_dir,
        )
        result = run_pipeline(run_config)
        num_devices = len(result.placement.devices)

        for freq in base.frequencies_hz:
            graph = result.path_loss_graphs.get(freq)
            if graph is None:
                continue
            stats = _extract_graph_stats(graph, freq, num_devices)
            s = all_stats[freq]
            s['viable_fracs'].append(stats['viable_frac'])
            s['path_losses'].extend(stats['path_losses'])
            s['rx_powers'].extend(stats['rx_powers'])
            s['walls'].extend(stats['walls'])
            s['isolated_fracs'].append(stats['isolated_frac'])
            s['connectivities'].append(stats['connectivity'])
            s['total_pairs'] = stats['total_pairs']

        if config.save_individual:
            out_path = os.path.join(config.output_dir, f"run_{i:04d}.json")
            result.save_json(out_path)

    per_frequency = {}
    for freq, s in all_stats.items():
        per_frequency[freq] = FrequencyBandSummary(
            frequency_hz=freq,
            total_device_pairs=s['total_pairs'],
            viable_link_fraction=StatSummary.from_array(s['viable_fracs']),
            mean_path_loss_db=StatSummary.from_array(s['path_losses']),
            mean_rx_power_dbm=StatSummary.from_array(s['rx_powers']),
            mean_walls_crossed=StatSummary.from_array(s['walls']),
            isolated_device_fraction=StatSummary.from_array(s['isolated_fracs']),
            network_connectivity=StatSummary.from_array(s['connectivities']),
        )

    return BatchSummary(
        num_runs=config.num_runs,
        building_type=base.building_type.value,
        total_sqft=base.total_sqft,
        frequencies_hz=base.frequencies_hz,
        per_frequency=per_frequency,
    )
