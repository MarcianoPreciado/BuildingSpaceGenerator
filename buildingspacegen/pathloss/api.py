"""Public API for path loss computation."""
import os
from buildingspacegen.core.model import Building
from buildingspacegen.core.device import DevicePlacement
from buildingspacegen.core.links import PathLossGraph
from .graph import build_path_loss_graphs
from .materials import MaterialRFDatabase
from .models.multiwall import MultiWallPathLossModel


def _find_materials_yaml() -> str:
    """Find rf_materials.yaml, searching the same candidates as pipeline._find_data_dir."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, '..', '..', 'data', 'materials', 'rf_materials.yaml'),
        os.path.join(here, '..', 'data', 'materials', 'rf_materials.yaml'),
        os.path.join(os.getcwd(), 'data', 'materials', 'rf_materials.yaml'),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    raise FileNotFoundError(
        f"Cannot find rf_materials.yaml. Tried: {candidates}"
    )


def compute_path_loss(
    building: Building,
    placement: DevicePlacement,
    frequencies_hz: list,
    seed: int = None,
    run_index: int = 0,
    materials_yaml: str = None,
) -> PathLossGraph:
    """
    Compute path loss for all device pairs across all requested frequencies.

    Args:
        building: Building model.
        placement: Device placement result.
        frequencies_hz: List of RF frequencies in Hz.
        seed: Random seed for stochastic wall attenuation.
               Defaults to building.seed when not supplied.
        run_index: Run index for Monte Carlo multi-run simulations.
        materials_yaml: Path to rf_materials.yaml; auto-detected when None.

    Returns:
        A single PathLossGraph containing link results for every frequency.
    """
    if seed is None:
        seed = getattr(building, 'seed', 42)

    materials_path = materials_yaml or _find_materials_yaml()
    material_db = MaterialRFDatabase.from_yaml(materials_path)
    model = MultiWallPathLossModel(material_db)

    graphs = build_path_loss_graphs(
        building=building,
        placement=placement,
        model=model,
        material_db=material_db,
        frequencies_hz=frequencies_hz,
        seed=seed,
        run_index=run_index,
    )

    # Merge all per-frequency graphs into one PathLossGraph so callers
    # get a single object regardless of how many bands were requested.
    merged = PathLossGraph()
    for graph in graphs.values():
        for link in graph.all_links:
            merged.add_link(link)
    return merged
