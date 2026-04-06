"""Base generator interface."""
from abc import ABC, abstractmethod
from typing import Optional

try:
    from core import Building, BuildingType
    from buildinggen.archetypes import Archetype
except ImportError:
    from ...core import Building, BuildingType
    from ..archetypes import Archetype


class BuildingGenerator(ABC):
    """Base class for building generators."""

    @abstractmethod
    def generate(
        self,
        building_type: BuildingType,
        total_sqft: float,
        num_floors: int,
        seed: int,
        archetype: Optional[Archetype] = None,
    ) -> Building:
        """Generate a building.

        Args:
            building_type: Type of building
            total_sqft: Total building area in square feet
            num_floors: Number of floors
            seed: Random seed for reproducibility
            archetype: Optional archetype override

        Returns:
            Generated Building
        """
        pass
