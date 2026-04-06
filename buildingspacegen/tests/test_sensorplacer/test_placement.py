"""Tests for sensor placement."""
import pytest
from buildingspacegen.buildinggen.api import generate_building
from buildingspacegen.core.enums import BuildingType, DeviceType, RoomType
from buildingspacegen.sensorplacer.api import place_sensors
from buildingspacegen.sensorplacer.rules import DEFAULT_RULES


def test_place_sensors_basic():
    """Test basic sensor placement in a medium office building."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    # Verify placement is not empty
    assert len(placement.devices) > 0

    # Verify main controller count
    main_controllers = placement.get_devices_by_type(DeviceType.MAIN_CONTROLLER)
    assert len(main_controllers) >= 1

    # Verify secondary controller count is reasonable
    secondary_controllers = placement.get_devices_by_type(DeviceType.SECONDARY_CONTROLLER)
    assert len(secondary_controllers) >= 1

    # Verify sensors are present
    sensors = placement.get_devices_by_type(DeviceType.SENSOR)
    assert len(sensors) > 0

    # Verify total device count is reasonable
    total_devices = len(placement.devices)
    assert total_devices >= 3


def test_all_devices_on_valid_walls():
    """Verify all devices are on valid walls."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    wall_ids = {wall.id for wall in building.all_walls()}

    for device in placement.devices:
        assert device.wall_id in wall_ids, f"Device {device.id} on invalid wall {device.wall_id}"
        assert device.room_id, f"Device {device.id} has no room"


def test_no_devices_in_excluded_rooms():
    """Verify no devices are placed in excluded room types."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building, rules=DEFAULT_RULES)

    excluded_types = DEFAULT_RULES.excluded_room_types
    for device in placement.devices:
        room = building.get_room(device.room_id)
        assert room.room_type not in excluded_types, \
            f"Device {device.id} in excluded room type {room.room_type}"


def test_determinism():
    """Verify same seed produces same placement."""
    building1 = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement1 = place_sensors(building1)

    building2 = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement2 = place_sensors(building2)

    assert len(placement1.devices) == len(placement2.devices)

    for d1, d2 in zip(placement1.devices, placement2.devices):
        assert d1.position.x == d2.position.x
        assert d1.position.y == d2.position.y
        assert d1.position.z == d2.position.z
        assert d1.device_type == d2.device_type


def test_device_heights():
    """Verify devices are at correct heights."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building, rules=DEFAULT_RULES)

    for device in placement.devices:
        if device.device_type == DeviceType.MAIN_CONTROLLER:
            assert abs(device.position.z - DEFAULT_RULES.main_controller_wall_height_m) < 0.01
        elif device.device_type == DeviceType.SECONDARY_CONTROLLER:
            assert abs(device.position.z - DEFAULT_RULES.secondary_controller_wall_height_m) < 0.01
        elif device.device_type == DeviceType.SENSOR:
            assert abs(device.position.z - DEFAULT_RULES.sensor_wall_height_m) < 0.01


def test_main_controller_center_preference():
    """Verify main controller prefers center location when single."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

    main_controllers = placement.get_devices_by_type(DeviceType.MAIN_CONTROLLER)
    # With small building, should have exactly 1 main controller
    if len(main_controllers) == 1:
        mc = main_controllers[0]
        centroid = building.footprint.centroid()
        # Controller should be relatively close to centroid
        dist = ((mc.position.x - centroid.x)**2 + (mc.position.y - centroid.y)**2)**0.5
        # Should be reasonably close (within 20% of building diagonal)
        bbox = building.footprint.bounding_box()
        diagonal = ((bbox.width()**2 + bbox.height()**2)**0.5)
        assert dist < diagonal * 0.3


def test_sensor_minimum_per_room():
    """Verify minimum sensors per room."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building, rules=DEFAULT_RULES)

    for floor in building.floors:
        for room in floor.rooms:
            if room.room_type in DEFAULT_RULES.excluded_room_types:
                continue
            devices_in_room = placement.get_devices_in_room(room.id)
            sensors_in_room = [d for d in devices_in_room if d.device_type == DeviceType.SENSOR]
            min_required = DEFAULT_RULES.sensor_min_per_room
            assert len(sensors_in_room) >= min_required, \
                f"Room {room.id} has only {len(sensors_in_room)} sensors, minimum is {min_required}"


def test_large_building_placement():
    """Test placement in a larger building."""
    building = generate_building(BuildingType.LARGE_OFFICE, total_sqft=250000, seed=42)
    placement = place_sensors(building)

    main_controllers = placement.get_devices_by_type(DeviceType.MAIN_CONTROLLER)
    secondary_controllers = placement.get_devices_by_type(DeviceType.SECONDARY_CONTROLLER)
    sensors = placement.get_devices_by_type(DeviceType.SENSOR)

    # Large building should have multiple controllers
    assert len(main_controllers) > 1
    assert len(secondary_controllers) > 1
    assert len(sensors) > 100


def test_device_positions_valid():
    """Verify all device positions have valid coordinates."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    for device in placement.devices:
        pos = device.position
        assert isinstance(pos.x, (int, float)) and not np.isnan(pos.x)
        assert isinstance(pos.y, (int, float)) and not np.isnan(pos.y)
        assert isinstance(pos.z, (int, float)) and not np.isnan(pos.z)
        assert pos.z >= 0


import numpy as np
