"""Enums for BuildingSpaceGenerator."""
from enum import Enum


class BuildingType(Enum):
    MEDIUM_OFFICE = "medium_office"
    LARGE_OFFICE = "large_office"
    WAREHOUSE = "warehouse"


class RoomType(Enum):
    OPEN_OFFICE = "open_office"
    PRIVATE_OFFICE = "private_office"
    CONFERENCE = "conference"
    LOBBY = "lobby"
    CORRIDOR = "corridor"
    RESTROOM = "restroom"
    KITCHEN_BREAK = "kitchen_break"
    MECHANICAL = "mechanical"
    IT_SERVER = "it_server"
    STORAGE = "storage"
    WAREHOUSE_BAY = "warehouse_bay"
    LOADING_DOCK = "loading_dock"
    STAIRWELL = "stairwell"
    ELEVATOR = "elevator"


class WallMaterial(Enum):
    GYPSUM_SINGLE = "gypsum_single"
    GYPSUM_DOUBLE = "gypsum_double"
    CONCRETE_BLOCK = "concrete_block"
    REINFORCED_CONCRETE = "reinforced_concrete"
    BRICK = "brick"
    GLASS_STANDARD = "glass_standard"
    GLASS_LOW_E = "glass_low_e"
    WOOD_DOOR = "wood_door"
    METAL_FIRE_DOOR = "metal_fire_door"
    ELEVATOR_SHAFT = "elevator_shaft"


class DeviceType(Enum):
    MAIN_CONTROLLER = "main_controller"
    SECONDARY_CONTROLLER = "secondary_controller"
    SENSOR = "sensor"


# Room type metadata
ROOM_TYPE_METADATA: dict = {
    RoomType.OPEN_OFFICE: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 20.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.1,
    },
    RoomType.PRIVATE_OFFICE: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 10.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.1,
    },
    RoomType.CONFERENCE: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 15.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.3,
    },
    RoomType.LOBBY: {
        "default_ceiling_height_m": 4.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 20.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.1,
    },
    RoomType.CORRIDOR: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 5.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.05,
    },
    RoomType.RESTROOM: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 8.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.05,
    },
    RoomType.KITCHEN_BREAK: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 15.0,
        "can_have_windows": True,
        "typical_occupancy_per_sqm": 0.15,
    },
    RoomType.MECHANICAL: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.CONCRETE_BLOCK,
        "min_area_sqm": 10.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.01,
    },
    RoomType.IT_SERVER: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.CONCRETE_BLOCK,
        "min_area_sqm": 10.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.02,
    },
    RoomType.STORAGE: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.GYPSUM_DOUBLE,
        "min_area_sqm": 5.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.01,
    },
    RoomType.WAREHOUSE_BAY: {
        "default_ceiling_height_m": 8.0,
        "interior_wall_material": WallMaterial.CONCRETE_BLOCK,
        "min_area_sqm": 100.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.02,
    },
    RoomType.LOADING_DOCK: {
        "default_ceiling_height_m": 5.0,
        "interior_wall_material": WallMaterial.CONCRETE_BLOCK,
        "min_area_sqm": 30.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.02,
    },
    RoomType.STAIRWELL: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.REINFORCED_CONCRETE,
        "min_area_sqm": 8.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.01,
    },
    RoomType.ELEVATOR: {
        "default_ceiling_height_m": 3.0,
        "interior_wall_material": WallMaterial.ELEVATOR_SHAFT,
        "min_area_sqm": 4.0,
        "can_have_windows": False,
        "typical_occupancy_per_sqm": 0.0,
    },
}
