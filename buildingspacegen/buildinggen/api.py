"""Public API for building generation."""
from typing import Optional
from pathlib import Path

try:
    from core import Building, BuildingType
except ImportError:
    from ..core import Building, BuildingType
from .archetypes import get_default_registry
from .generators import BSPGenerator


def generate_building(
    building_type: BuildingType,
    total_sqft: float,
    num_floors: int = 1,
    seed: int = 42,
    generator: str = "bsp",
    archetype_overrides: Optional[dict] = None,
) -> Building:
    """Generate a building.

    Args:
        building_type: Type of building (from BuildingType enum)
        total_sqft: Total building area in square feet
        num_floors: Number of floors (default 1)
        seed: Random seed for reproducibility (default 42)
        generator: Generator type, "bsp" (default) or custom
        archetype_overrides: Optional dict of archetype parameters to override

    Returns:
        Generated Building object

    Raises:
        ValueError: If invalid parameters
        KeyError: If building type not supported
    """
    registry = get_default_registry()
    try:
        archetype = registry.get_by_enum(building_type)
    except KeyError:
        default_dir = Path(__file__).resolve().parents[1] / "data" / "archetypes"
        if default_dir.exists():
            registry.load_from_directory(str(default_dir))
        archetype = registry.get_by_enum(building_type)

    # Apply overrides if provided
    if archetype_overrides:
        # For now, just use base archetype
        # Could apply overrides to archetype fields
        pass

    # Create and run generator
    if generator == "bsp":
        gen = BSPGenerator()
    else:
        raise ValueError(f"Unknown generator: {generator}")

    building = gen.generate(
        building_type=building_type,
        total_sqft=total_sqft,
        num_floors=num_floors,
        seed=seed,
        archetype=archetype,
    )

    return building


def load_archetype_directory(dirpath: str) -> None:
    """Load archetypes from a directory.

    Args:
        dirpath: Path to directory containing YAML archetype files
    """
    registry = get_default_registry()
    registry.load_from_directory(dirpath)
