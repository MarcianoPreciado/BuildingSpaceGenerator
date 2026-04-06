"""Tests for the additive device mount contract."""
from buildingspacegen.core import (
    Building,
    BuildingType,
    Device,
    DevicePlacement,
    DeviceType,
    Floor,
    PlacementRules,
    Point2D,
    Point3D,
    Polygon2D,
    RadioProfile,
    Room,
    RoomType,
    serialize_building_scene,
    deserialize_building_scene,
)


def _make_building() -> Building:
    footprint = Polygon2D([
        Point2D(0, 0),
        Point2D(8, 0),
        Point2D(8, 8),
        Point2D(0, 8),
    ])
    room_poly = Polygon2D([
        Point2D(0, 0),
        Point2D(8, 0),
        Point2D(8, 8),
        Point2D(0, 8),
    ])
    room = Room(
        id="room_001",
        room_type=RoomType.OPEN_OFFICE,
        polygon=room_poly,
        floor_index=0,
        wall_ids=[],
        door_ids=[],
        ceiling_height=3.0,
    )
    floor = Floor(
        index=0,
        rooms=[room],
        walls=[],
        doors=[],
        elevation=0.0,
        footprint=footprint,
    )
    return Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=688.0,
        seed=42,
    )


def test_device_mount_metadata_defaults() -> None:
    profile = RadioProfile(
        name="test_profile",
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=2.0,
        rx_antenna_gain_dbi=2.0,
        rx_sensitivity_dbm=-95.0,
        supported_frequencies_hz=[900e6],
    )
    device = Device(
        id="dev_001",
        device_type=DeviceType.SENSOR,
        position=Point3D(1.0, 2.0, 1.5),
        room_id="room_001",
        wall_id="wall_001",
        radio_profile=profile,
    )

    assert device.position_along_wall is None
    assert device.mounted_side is None
    assert device.offset_from_wall_m == 0.0


def test_device_mount_metadata_round_trip() -> None:
    building = _make_building()
    profile = RadioProfile(
        name="test_profile",
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=2.0,
        rx_antenna_gain_dbi=2.0,
        rx_sensitivity_dbm=-95.0,
        supported_frequencies_hz=[900e6],
    )
    device = Device(
        id="dev_001",
        device_type=DeviceType.SENSOR,
        position=Point3D(1.0, 2.0, 1.5),
        room_id="room_001",
        wall_id="wall_001",
        radio_profile=profile,
        position_along_wall=0.37,
        mounted_side="left",
        offset_from_wall_m=0.12,
    )
    placement = DevicePlacement(
        building_seed=building.seed,
        devices=[device],
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

    scene = serialize_building_scene(building, placement, radio_profiles={profile.name: profile})
    restored_building, restored_placement, _ = deserialize_building_scene(scene)

    assert restored_building.seed == building.seed
    assert restored_placement is not None
    restored_device = restored_placement.devices[0]
    assert restored_device.position_along_wall == 0.37
    assert restored_device.mounted_side == "left"
    assert restored_device.offset_from_wall_m == 0.12
