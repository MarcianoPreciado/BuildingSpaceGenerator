"""Default placement rules."""
from buildingspacegen.core.device import PlacementRules
from buildingspacegen.core.enums import RoomType

DEFAULT_WALL_MOUNT_OFFSET_M = 0.12


DEFAULT_RULES = PlacementRules(
    main_controller_per_sqft=1/25000,
    main_controller_wall_height_m=2.0,
    main_controller_prefer_center=True,
    secondary_controller_per_sqft=1/5000,
    secondary_controller_wall_height_m=2.0,
    sensor_min_per_room=1,
    sensor_per_sqft=1/500,
    sensor_wall_height_m=1.5,
    sensor_min_spacing_m=2.0,
    excluded_room_types=[RoomType.CORRIDOR, RoomType.ELEVATOR, RoomType.STAIRWELL],
)
setattr(DEFAULT_RULES, "wall_mount_offset_m", DEFAULT_WALL_MOUNT_OFFSET_M)


def get_wall_mount_offset(rules: PlacementRules) -> float:
    """Return the configured wall-mount inset, falling back to the project default."""
    return float(getattr(rules, "wall_mount_offset_m", DEFAULT_WALL_MOUNT_OFFSET_M))
