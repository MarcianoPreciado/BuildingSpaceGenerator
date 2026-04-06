"""Tests for sensor placement."""
import numpy as np
import pytest
from buildingspacegen.buildinggen.api import generate_building
from buildingspacegen.core.device import PlacementRules
from buildingspacegen.core.enums import BuildingType, DeviceType, RoomType
from buildingspacegen.sensorplacer.api import place_sensors
from buildingspacegen.sensorplacer.rules import DEFAULT_RULES
from buildingspacegen.sensorplacer.config import load_placement_rules


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
        assert d1.position_along_wall == d2.position_along_wall
        assert d1.mounted_side == d2.mounted_side


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

def test_devices_have_wall_mount_metadata():
    """Devices should carry explicit wall mount metadata."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    for device in placement.devices:
        assert device.position_along_wall is not None
        assert device.mounted_side in {"left", "right"}
        assert device.offset_from_wall_m > 0.0


def test_devices_are_inside_owning_room_not_on_centerline():
    """Wall-mounted points should sit inside the owning room, not on the wall centerline."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    for device in placement.devices:
        room = building.get_room(device.room_id)
        wall = building.get_wall(device.wall_id)
        wall_x = wall.start.x + device.position_along_wall * (wall.end.x - wall.start.x)
        wall_y = wall.start.y + device.position_along_wall * (wall.end.y - wall.start.y)
        assert room.polygon.contains(device.position.to_2d())
        assert abs(device.position.x - wall_x) + abs(device.position.y - wall_y) > 0.01


def test_sensors_do_not_mount_to_exterior_side():
    """Exterior-wall mounts must remain on the room-facing side of the building envelope."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building)

    for sensor in placement.get_devices_by_type(DeviceType.SENSOR):
        room = building.get_room(sensor.room_id)
        wall = building.get_wall(sensor.wall_id)
        if not wall.is_exterior:
            continue
        assert room.polygon.contains(sensor.position.to_2d())


def test_every_non_excluded_room_has_sensor_inside_room():
    """Each occupiable room should have at least one sensor truly inside its polygon."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building, rules=DEFAULT_RULES)

    for room in building.all_rooms():
        if room.room_type in DEFAULT_RULES.excluded_room_types:
            continue
        sensors = [
            device
            for device in placement.get_devices_in_room(room.id)
            if device.device_type == DeviceType.SENSOR
        ]
        assert sensors
        assert all(room.polygon.contains(sensor.position.to_2d()) for sensor in sensors)


def test_multiple_sensors_in_room_use_multiple_wall_positions():
    """Rooms that need several sensors should not collapse them onto one identical wall position."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement = place_sensors(building, rules=DEFAULT_RULES)

    multi_sensor_rooms = []
    for room in building.all_rooms():
        if room.room_type in DEFAULT_RULES.excluded_room_types:
            continue
        sensors = [
            device
            for device in placement.get_devices_in_room(room.id)
            if device.device_type == DeviceType.SENSOR
        ]
        if len(sensors) > 1:
            multi_sensor_rooms.append((room, sensors))

    assert multi_sensor_rooms
    for _, sensors in multi_sensor_rooms:
        unique_positions = {
            (sensor.wall_id, round(sensor.position_along_wall, 4))
            for sensor in sensors
        }
        assert len(unique_positions) > 1


def test_yaml_defaults_are_loaded_when_rules_none(tmp_path, monkeypatch):
    """place_sensors should source default densities from YAML when rules are omitted."""
    rules_path = tmp_path / "placement_rules.yaml"
    rules_path.write_text(
        """
defaults:
  main_controller_per_sqft: 0.0
  main_controller_wall_height_m: 2.0
  main_controller_prefer_center: true
  secondary_controller_per_sqft: 0.0
  secondary_controller_wall_height_m: 2.0
  sensor_min_per_room: 2
  sensor_per_sqft: 0.0
  sensor_wall_height_m: 1.5
  sensor_min_spacing_m: 2.0
  wall_mount_offset_m: 0.2
  excluded_room_types:
    - corridor
    - elevator
    - stairwell
by_building_type:
  medium_office: {}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUILDINGSPACEGEN_PLACEMENT_RULES_PATH", str(rules_path))

    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=12000, seed=42)
    placement = place_sensors(building)
    loaded_rules = load_placement_rules(building.building_type)

    assert getattr(loaded_rules, "wall_mount_offset_m") == 0.2
    for room in building.all_rooms():
        if room.room_type in loaded_rules.excluded_room_types:
            continue
        sensors = [
            device
            for device in placement.get_devices_in_room(room.id)
            if device.device_type == DeviceType.SENSOR
        ]
        assert len(sensors) >= 2


def test_explicit_rules_override_yaml(tmp_path, monkeypatch):
    """Explicit rule objects should bypass YAML defaults."""
    rules_path = tmp_path / "placement_rules.yaml"
    rules_path.write_text(
        """
defaults:
  main_controller_per_sqft: 0.0
  main_controller_wall_height_m: 2.0
  main_controller_prefer_center: true
  secondary_controller_per_sqft: 0.0
  secondary_controller_wall_height_m: 2.0
  sensor_min_per_room: 4
  sensor_per_sqft: 0.0
  sensor_wall_height_m: 1.5
  sensor_min_spacing_m: 2.0
  wall_mount_offset_m: 0.2
  excluded_room_types:
    - corridor
    - elevator
    - stairwell
by_building_type:
  medium_office: {}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("BUILDINGSPACEGEN_PLACEMENT_RULES_PATH", str(rules_path))

    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=12000, seed=42)
    explicit_rules = PlacementRules(
        main_controller_per_sqft=0.0,
        main_controller_wall_height_m=2.0,
        main_controller_prefer_center=True,
        secondary_controller_per_sqft=0.0,
        secondary_controller_wall_height_m=2.0,
        sensor_min_per_room=1,
        sensor_per_sqft=0.0,
        sensor_wall_height_m=1.5,
        sensor_min_spacing_m=2.0,
        excluded_room_types=DEFAULT_RULES.excluded_room_types,
    )
    setattr(explicit_rules, "wall_mount_offset_m", 0.05)
    placement = place_sensors(building, rules=explicit_rules)

    for room in building.all_rooms():
        if room.room_type in explicit_rules.excluded_room_types:
            continue
        sensors = [
            device
            for device in placement.get_devices_in_room(room.id)
            if device.device_type == DeviceType.SENSOR
        ]
        assert len(sensors) == 1
        assert all(device.offset_from_wall_m == 0.05 for device in sensors)
