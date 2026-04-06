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
]
