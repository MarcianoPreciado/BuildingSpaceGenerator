"""Tests for serialization."""
import json
from buildingspacegen.core import (
    Building, Floor, Room, WallSegment, Door, Material, Point2D, Polygon2D,
    BuildingType, RoomType, WallMaterial, Point3D,
    Device, DevicePlacement, RadioProfile, PlacementRules, DeviceType,
    serialize_building_scene, deserialize_building_scene,
    building_to_dict, building_from_dict,
)


def create_simple_building() -> Building:
    """Create a simple test building."""
    # Create room polygon
    room_poly = Polygon2D([
        Point2D(0, 0),
        Point2D(10, 0),
        Point2D(10, 10),
        Point2D(0, 10),
    ])

    # Create room
    room = Room(
        id="room_001",
        room_type=RoomType.OPEN_OFFICE,
        polygon=room_poly,
        floor_index=0,
        wall_ids=["wall_001"],
        door_ids=["door_001"],
        ceiling_height=3.0,
    )

    # Create wall
    wall = WallSegment(
        id="wall_001",
        start=Point2D(0, 0),
        end=Point2D(10, 0),
        height=3.0,
        materials=[Material("gypsum_double", 0.026)],
        is_exterior=False,
        room_ids=("room_001", "room_002"),
    )

    # Create door
    door = Door(
        id="door_001",
        wall_id="wall_001",
        position_along_wall=0.5,
        width=0.9,
        height=2.1,
        material=Material("wood_door", 0.045),
    )

    # Create floor
    footprint = Polygon2D([
        Point2D(0, 0),
        Point2D(20, 0),
        Point2D(20, 20),
        Point2D(0, 20),
    ])

    floor = Floor(
        index=0,
        rooms=[room],
        walls=[wall],
        doors=[door],
        elevation=0.0,
        footprint=footprint,
    )

    # Create building
    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=2150,  # ~200 sqm
        seed=42,
    )

    return building


class TestSerialization:
    def test_building_to_dict(self):
        building = create_simple_building()
        data = building_to_dict(building)

        assert data["building_type"] == "medium_office"
        assert data["seed"] == 42
        assert len(data["floors"]) == 1
        assert len(data["floors"][0]["rooms"]) == 1

    def test_building_from_dict(self):
        building = create_simple_building()
        data = building_to_dict(building)
        restored = building_from_dict(data)

        assert restored.building_type == building.building_type
        assert restored.seed == building.seed
        assert len(restored.floors) == 1

    def test_round_trip_building(self):
        building = create_simple_building()
        data = building_to_dict(building)
        restored = building_from_dict(data)
        data2 = building_to_dict(restored)

        assert data == data2

    def test_serialize_building_scene(self):
        building = create_simple_building()
        scene = serialize_building_scene(building)

        assert "building" in scene
        assert "devices" in scene
        assert "radio_profiles" in scene
        assert "links" in scene
        assert scene["devices"] is None
        assert scene["radio_profiles"] is None
        assert scene["links"] is None

    def test_scene_json_structure(self):
        building = create_simple_building()
        scene = serialize_building_scene(building)
        json_str = json.dumps(scene)
        data = json.loads(json_str)

        assert data["building"]["building_type"] == "medium_office"
        assert data["building"]["seed"] == 42

    def test_room_area_calculations(self):
        building = create_simple_building()
        room = building.floors[0].rooms[0]

        # 10x10 = 100 sqm
        assert abs(room.area_sqm - 100.0) < 0.1
        # ~1076.4 sqft
        assert abs(room.area_sqft - 1076.4) < 1.0

    def test_device_mount_fields_round_trip(self):
        building = create_simple_building()
        profile = RadioProfile(
            name="test_profile",
            tx_power_dbm=10.0,
            tx_antenna_gain_dbi=1.0,
            rx_antenna_gain_dbi=1.0,
            rx_sensitivity_dbm=-100.0,
            supported_frequencies_hz=[900e6],
        )
        placement = DevicePlacement(
            building_seed=building.seed,
            devices=[
                Device(
                    id="dev_001",
                    device_type=DeviceType.SENSOR,
                    position=Point3D(0.12, 5.0, 1.5),
                    room_id="room_001",
                    wall_id="wall_001",
                    radio_profile=profile,
                    position_along_wall=0.5,
                    mounted_side="left",
                    offset_from_wall_m=0.12,
                )
            ],
            placement_rules=PlacementRules(
                main_controller_per_sqft=0.0,
                main_controller_wall_height_m=2.0,
                main_controller_prefer_center=True,
                secondary_controller_per_sqft=0.0,
                secondary_controller_wall_height_m=2.0,
                sensor_min_per_room=1,
                sensor_per_sqft=0.0,
                sensor_wall_height_m=1.5,
                sensor_min_spacing_m=2.0,
            ),
        )

        scene = serialize_building_scene(
            building,
            devices=placement,
            radio_profiles={profile.name: profile},
        )
        restored_building, restored_devices, _ = deserialize_building_scene(scene)

        assert restored_building.seed == building.seed
        assert restored_devices is not None
        restored = restored_devices.devices[0]
        assert restored.position_along_wall == 0.5
        assert restored.mounted_side == "left"
        assert restored.offset_from_wall_m == 0.12

    def test_device_mount_fields_backward_compatible(self):
        building = create_simple_building()
        scene = {
            "building": building_to_dict(building),
            "devices": [
                {
                    "id": "dev_001",
                    "device_type": "sensor",
                    "position": [1.0, 2.0, 1.5],
                    "room_id": "room_001",
                    "wall_id": "wall_001",
                    "radio_profile_name": "test_profile",
                    "metadata": {},
                }
            ],
            "radio_profiles": {
                "test_profile": {
                    "name": "test_profile",
                    "tx_power_dbm": 10.0,
                    "tx_antenna_gain_dbi": 1.0,
                    "rx_antenna_gain_dbi": 1.0,
                    "rx_sensitivity_dbm": -100.0,
                    "supported_frequencies_hz": [900e6],
                }
            },
            "links": None,
            "simulation": None,
        }

        _, restored_devices, _ = deserialize_building_scene(scene)

        assert restored_devices is not None
        restored = restored_devices.devices[0]
        assert restored.position_along_wall is None
        assert restored.mounted_side is None
        assert restored.offset_from_wall_m == 0.0

    def test_device_metadata_round_trip(self):
        building = create_simple_building()
        profile = RadioProfile(
            name="test_profile",
            tx_power_dbm=10.0,
            tx_antenna_gain_dbi=1.0,
            rx_antenna_gain_dbi=1.0,
            rx_sensitivity_dbm=-100.0,
            supported_frequencies_hz=[900e6, 2.4e9],
        )
        placement = DevicePlacement(
            building_seed=building.seed,
            devices=[
                Device(
                    id="dev_001",
                    device_type=DeviceType.SENSOR,
                    position=Point3D(1.0, 2.0, 1.5),
                    room_id="room_001",
                    wall_id="",
                    radio_profile=profile,
                    metadata={
                        "has_viable_controller_link": False,
                        "viable_controller_link_frequencies_hz": [],
                    },
                )
            ],
            placement_rules=PlacementRules(
                main_controller_per_sqft=0.0,
                main_controller_wall_height_m=2.0,
                main_controller_prefer_center=True,
                secondary_controller_per_sqft=0.0,
                secondary_controller_wall_height_m=2.0,
                sensor_min_per_room=1,
                sensor_per_sqft=0.0,
                sensor_wall_height_m=1.5,
                sensor_min_spacing_m=2.0,
            ),
        )

        scene = serialize_building_scene(
            building,
            devices=placement,
            radio_profiles={profile.name: profile},
        )
        _, restored_devices, _ = deserialize_building_scene(scene)

        assert restored_devices is not None
        restored = restored_devices.devices[0]
        assert restored.metadata["has_viable_controller_link"] is False
        assert restored.metadata["viable_controller_link_frequencies_hz"] == []
