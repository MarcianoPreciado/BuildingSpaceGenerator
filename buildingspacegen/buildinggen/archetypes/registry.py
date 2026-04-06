"""Archetype registry and loader."""
from pathlib import Path
from typing import Optional

try:
    from core.enums import BuildingType
except ImportError:
    from ...core.enums import BuildingType
from .archetype import Archetype


class ArchetypeRegistry:
    """Registry of building archetypes."""

    def __init__(self):
        """Initialize empty registry."""
        self._archetypes: dict[str, Archetype] = {}

    def register(self, building_type: str, archetype: Archetype) -> None:
        """Register an archetype."""
        self._archetypes[building_type] = archetype

    def get(self, building_type: str) -> Archetype:
        """Get archetype by building type string."""
        if building_type not in self._archetypes:
            raise KeyError(f"No archetype registered for {building_type}")
        return self._archetypes[building_type]

    def get_by_enum(self, building_type: BuildingType) -> Archetype:
        """Get archetype by BuildingType enum."""
        return self.get(building_type.value)

    def load_from_directory(self, dirpath: str) -> None:
        """Load all YAML files from directory."""
        dirpath_obj = Path(dirpath)
        for yaml_file in dirpath_obj.glob("*.yaml"):
            archetype = Archetype.from_yaml_file(str(yaml_file))
            archetype.validate()
            self.register(archetype.building_type_str, archetype)


# Global registry instance
_DEFAULT_REGISTRY = ArchetypeRegistry()


def get_default_registry() -> ArchetypeRegistry:
    """Get the default global registry."""
    return _DEFAULT_REGISTRY
