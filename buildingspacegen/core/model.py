"""Core data model for BuildingSpaceGenerator."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Iterator

from .geometry import Point2D, Polygon2D
from .enums import BuildingType, RoomType, WallMaterial


@dataclass
class Material:
    """Wall material with thickness."""
    name: str  # Maps to WallMaterial.value
    thickness_m: float


@dataclass
class WallSegment:
    """Interior or exterior wall segment."""
    id: str
    start: Point2D
    end: Point2D
    height: float
    materials: list[Material]
    is_exterior: bool
    room_ids: tuple[str, Optional[str]]  # (room_a, room_b) where room_b is None for exterior


@dataclass
class Door:
    """Door in a wall."""
    id: str
    wall_id: str
    position_along_wall: float  # 0.0 to 1.0
    width: float
    height: float
    material: Material


@dataclass
class Room:
    """Room within a floor."""
    id: str
    room_type: RoomType
    polygon: Polygon2D
    floor_index: int
    wall_ids: list[str]
    door_ids: list[str]
    ceiling_height: float
    metadata: dict = field(default_factory=dict)

    @property
    def area_sqft(self) -> float:
        """Get room area in square feet."""
        area_sqm = self.polygon.area()
        return area_sqm * 10.764  # 1 sqm = 10.764 sqft

    @property
    def area_sqm(self) -> float:
        """Get room area in square meters."""
        return self.polygon.area()


@dataclass
class Floor:
    """Single floor of a building."""
    index: int
    rooms: list[Room]
    walls: list[WallSegment]
    doors: list[Door]
    elevation: float
    footprint: Polygon2D


@dataclass
class Building:
    """Complete building model."""
    building_type: BuildingType
    floors: list[Floor]
    footprint: Polygon2D
    total_area_sqft: float
    seed: int
    metadata: dict = field(default_factory=dict)

    def all_rooms(self) -> Iterator[Room]:
        """Iterate over all rooms in the building."""
        for floor in self.floors:
            for room in floor.rooms:
                yield room

    def all_walls(self) -> Iterator[WallSegment]:
        """Iterate over all walls in the building."""
        for floor in self.floors:
            for wall in floor.walls:
                yield wall

    def all_doors(self) -> Iterator[Door]:
        """Iterate over all doors in the building."""
        for floor in self.floors:
            for door in floor.doors:
                yield door

    def get_room(self, room_id: str) -> Room:
        """Get room by ID."""
        for room in self.all_rooms():
            if room.id == room_id:
                return room
        raise KeyError(f"Room {room_id} not found")

    def get_wall(self, wall_id: str) -> WallSegment:
        """Get wall by ID."""
        for wall in self.all_walls():
            if wall.id == wall_id:
                return wall
        raise KeyError(f"Wall {wall_id} not found")

    def get_walls_for_room(self, room_id: str) -> list[WallSegment]:
        """Get all walls for a room."""
        room = self.get_room(room_id)
        walls = []
        for wall_id in room.wall_ids:
            walls.append(self.get_wall(wall_id))
        return walls

    def get_rooms_sharing_wall(self, wall_id: str) -> tuple[Room, Optional[Room]]:
        """Get rooms on either side of a wall."""
        wall = self.get_wall(wall_id)
        room_a = self.get_room(wall.room_ids[0])
        room_b = None
        if wall.room_ids[1] is not None:
            room_b = self.get_room(wall.room_ids[1])
        return (room_a, room_b)
