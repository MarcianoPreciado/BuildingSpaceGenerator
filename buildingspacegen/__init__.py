"""BuildingSpaceGenerator - Procedural building generator for wireless sensor networks."""
from .core import (
    Building, Room, Floor, WallSegment, Door, Material,
    Point2D, Point3D, Polygon2D, BBox,
    BuildingType, RoomType, WallMaterial, DeviceType,
    Device, RadioProfile, DevicePlacement,
    LinkResult, PathLossGraph,
    serialize_building_scene, deserialize_building_scene,
)
from .buildinggen import (
    generate_building, load_archetype_directory,
    Archetype, ArchetypeRegistry,
)
from .pipeline import ExistingBuildingPipelineConfig, ImportedPipelineConfig, run_existing_building_pipeline, run_imported_pipeline
from .sources.quantum import QuantumFloorSummary, list_quantum_floors, load_quantum_floor

__version__ = "0.1.0"

__all__ = [
    "Building", "Room", "Floor", "WallSegment", "Door", "Material",
    "Point2D", "Point3D", "Polygon2D", "BBox",
    "BuildingType", "RoomType", "WallMaterial", "DeviceType",
    "Device", "RadioProfile", "DevicePlacement",
    "LinkResult", "PathLossGraph",
    "serialize_building_scene", "deserialize_building_scene",
    "generate_building", "load_archetype_directory",
    "Archetype", "ArchetypeRegistry",
    "ExistingBuildingPipelineConfig", "ImportedPipelineConfig",
    "run_existing_building_pipeline", "run_imported_pipeline",
    "QuantumFloorSummary", "list_quantum_floors", "load_quantum_floor",
]
