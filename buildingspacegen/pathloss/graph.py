"""Path loss graph construction."""
import numpy as np
from buildingspacegen.core.model import Building
from buildingspacegen.core.device import DevicePlacement
from buildingspacegen.core.links import PathLossGraph
from .models.base import PathLossModel
from .materials import MaterialRFDatabase


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

    Args:
        building: Building model
        placement: Device placement
        model: Path loss model to use
        material_db: Material RF database
        frequency_hz: RF frequency in Hz
        seed: Random seed (per reproducibility contract)
        run_index: Run index for multi-run simulations

    Returns:
        PathLossGraph with all computed links
    """
    # Create RNG seeded with (seed + 1000 + run_index) per reproducibility contract
    rng = np.random.default_rng(seed + 1000 + run_index)

    # Pre-sample wall attenuations for this run
    wall_attenuations = {}
    for wall in building.all_walls():
        if wall.materials:
            mat_name = wall.materials[0].name
            atten = material_db.get_attenuation(mat_name, frequency_hz, rng)
            wall_attenuations[wall.id] = atten

    graph = PathLossGraph()
    devices = placement.devices
    n = len(devices)

    for i in range(n):
        for j in range(i + 1, n):
            tx = devices[i]
            rx = devices[j]

            link_fwd = model.compute_link(tx, rx, building, wall_attenuations, frequency_hz)
            graph.add_link(link_fwd)

            # Also compute reverse link (rx_power differs since profiles may differ)
            link_rev = model.compute_link(rx, tx, building, wall_attenuations, frequency_hz)
            graph.add_link(link_rev)

    return graph


def build_path_loss_graphs(
    building: Building,
    placement: DevicePlacement,
    model: PathLossModel,
    material_db: MaterialRFDatabase,
    frequencies_hz: list[float],
    seed: int,
    run_index: int = 0,
) -> dict[float, PathLossGraph]:
    """
    Build path loss graphs for multiple frequency bands.

    Args:
        building: Building model
        placement: Device placement
        model: Path loss model to use
        material_db: Material RF database
        frequencies_hz: List of RF frequencies in Hz
        seed: Random seed
        run_index: Run index for multi-run simulations

    Returns:
        Dictionary mapping frequency_hz to PathLossGraph
    """
    return {
        freq: build_path_loss_graph(building, placement, model, material_db, freq, seed, run_index)
        for freq in frequencies_hz
    }
