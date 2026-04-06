"""Core data model and geometry."""
from .geometry import Point2D, Point3D, LineSegment2D, Polygon2D, BBox
from .enums import (
    BuildingType, RoomType, WallMaterial, DeviceType, ROOM_TYPE_METADATA
)
from .model import (
    Material, WallSegment, Door, Room, Floor, Building
)
from .device import RadioProfile, Device, DevicePlacement, PlacementRules
from .links import LinkResult, PathLossGraph
from .serialization import (
    serialize_building_scene, deserialize_building_scene,
    building_to_dict, building_from_dict
)

__all__ = [
    "Point2D", "Point3D", "LineSegment2D", "Polygon2D", "BBox",
    "BuildingType", "RoomType", "WallMaterial", "DeviceType", "ROOM_TYPE_METADATA",
    "Material", "WallSegment", "Door", "Room", "Floor", "Building",
    "RadioProfile", "Device", "DevicePlacement", "PlacementRules",
    "LinkResult", "PathLossGraph",
    "serialize_building_scene", "deserialize_building_scene",
    "building_to_dict", "building_from_dict",
]
