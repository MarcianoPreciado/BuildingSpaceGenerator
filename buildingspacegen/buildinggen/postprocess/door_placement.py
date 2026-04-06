"""Door placement helpers extracted from the BSP generator."""
from __future__ import annotations

from typing import Sequence

import numpy as np

try:
    from core.model import Door, Material, Room, WallSegment
    from core.enums import RoomType
except ImportError:
    from ...core.model import Door, Material, Room, WallSegment
    from ...core.enums import RoomType


def choose_door_position_along_wall(
    wall: WallSegment,
    door_width: float,
    rng: np.random.Generator,
) -> float:
    """Choose a legal door center position along a wall."""
    wall_length = ((wall.end.x - wall.start.x) ** 2 + (wall.end.y - wall.start.y) ** 2) ** 0.5
    if wall_length <= 0.0:
        return 0.5

    min_t = door_width / wall_length
    max_t = 1.0 - min_t
    if min_t < max_t and wall_length >= 2.0 * door_width:
        return float(rng.uniform(min_t, max_t))
    return 0.5


def generate_doors(
    rooms: Sequence[Room],
    walls: Sequence[WallSegment],
    floor_idx: int,
    rng: np.random.Generator,
) -> list[Door]:
    """Generate doors between corridor and non-corridor spaces."""
    room_lookup = {room.id: room for room in rooms}
    doors: list[Door] = []
    counter = 0

    for wall in walls:
        if wall.is_exterior or wall.room_ids[1] is None:
            continue

        room_a = room_lookup[wall.room_ids[0]]
        room_b = room_lookup[wall.room_ids[1]]
        if room_a.room_type == RoomType.CORRIDOR and room_b.room_type == RoomType.CORRIDOR:
            continue
        if room_a.room_type != RoomType.CORRIDOR and room_b.room_type != RoomType.CORRIDOR:
            continue

        secure_types = {RoomType.MECHANICAL, RoomType.STAIRWELL, RoomType.IT_SERVER}
        material_name = "metal_fire_door" if {room_a.room_type, room_b.room_type} & secure_types else "wood_door"
        doors.append(
            Door(
                id=f"door_{floor_idx:03d}_{counter:03d}",
                wall_id=wall.id,
                position_along_wall=choose_door_position_along_wall(wall, 0.9, rng),
                width=0.9,
                height=2.1,
                material=Material(material_name, _get_material_thickness(material_name)),
            )
        )
        counter += 1

    return doors


def _get_material_thickness(material_name: str) -> float:
    thicknesses = {
        "gypsum_single": 0.016,
        "gypsum_double": 0.026,
        "concrete_block": 0.15,
        "reinforced_concrete": 0.20,
        "brick": 0.10,
        "glass_standard": 0.004,
        "glass_low_e": 0.004,
        "wood_door": 0.045,
        "metal_fire_door": 0.045,
        "elevator_shaft": 0.15,
    }
    return thicknesses.get(material_name, 0.05)
