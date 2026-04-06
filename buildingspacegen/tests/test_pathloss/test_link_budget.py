"""Tests for RF link budget calculations."""
import math
import os
import numpy as np
import pytest
from buildingspacegen.core.geometry import Point2D, Point3D, Polygon2D, LineSegment2D
from buildingspacegen.core.model import Building, Floor, Room, WallSegment, Material
from buildingspacegen.core.enums import BuildingType, RoomType
from buildingspacegen.core.device import Device, DevicePlacement, RadioProfile
from buildingspacegen.core.enums import DeviceType
from buildingspacegen.pathloss.materials import MaterialRFDatabase
from buildingspacegen.pathloss.models.multiwall import MultiWallPathLossModel


def get_materials_path():
    """Get path to materials YAML file."""
    return os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..',
        'data', 'materials', 'rf_materials.yaml'
    )


def create_simple_building():
    """Create a simple single-room building for testing."""
    # Create a simple square room
    footprint = Polygon2D([
        Point2D(0, 0),
        Point2D(20, 0),
        Point2D(20, 20),
        Point2D(0, 20),
    ])

    # Create walls for the room
    wall_north = WallSegment(
        id='wall_north',
        start=Point2D(0, 20),
        end=Point2D(20, 20),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', None),
    )
    wall_south = WallSegment(
        id='wall_south',
        start=Point2D(20, 0),
        end=Point2D(0, 0),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', None),
    )
    wall_east = WallSegment(
        id='wall_east',
        start=Point2D(20, 20),
        end=Point2D(20, 0),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', None),
    )
    wall_west = WallSegment(
        id='wall_west',
        start=Point2D(0, 0),
        end=Point2D(0, 20),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', None),
    )

    room = Room(
        id='room_0',
        room_type=RoomType.OPEN_OFFICE,
        polygon=footprint,
        floor_index=0,
        wall_ids=['wall_north', 'wall_south', 'wall_east', 'wall_west'],
        door_ids=[],
        ceiling_height=3.0,
    )

    floor = Floor(
        index=0,
        rooms=[room],
        walls=[wall_north, wall_south, wall_east, wall_west],
        doors=[],
        elevation=0.0,
        footprint=footprint,
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=400 * 10.764,  # 400 sqm in sqft
        seed=42,
    )

    return building


def create_simple_radio_profile():
    """Create a simple radio profile for testing."""
    return RadioProfile(
        name='test_profile',
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=2.0,
        rx_antenna_gain_dbi=2.0,
        rx_sensitivity_dbm=-95.0,
        supported_frequencies_hz=[900000000.0, 2400000000.0],
    )


def test_fspl_10m_2400mhz():
    """Test indoor baseline loss at 10m, 2.4 GHz."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    # Create two devices 10m apart inside the same room.
    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(2, 2, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(12, 2, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 2400000000.0)

    # Expected README baseline:
    # 20*log10(2.4e9) + 30*log10(10) + 20*log10(4*pi/c) + 12
    expected_base_loss = 82.05
    assert abs(link.fspl_db - expected_base_loss) < 0.5, \
        f"baseline loss mismatch: expected {expected_base_loss}, got {link.fspl_db}"

    # Wall loss should be 0 (no walls crossed)
    assert link.wall_loss_db == 0.0
    assert link.walls_crossed == 0

    # Path loss should equal the indoor baseline when no walls are crossed
    assert abs(link.path_loss_db - link.fspl_db) < 0.01


def test_fspl_10m_900mhz():
    """Test indoor baseline loss at 10m, 900 MHz."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(2, 2, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(12, 2, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 900000000.0)

    expected_base_loss = 76.53
    assert abs(link.fspl_db - expected_base_loss) < 0.5, \
        f"baseline loss mismatch: expected {expected_base_loss}, got {link.fspl_db}"


def test_distance_calculation():
    """Test 2D distance calculation in link."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(0, 0, 0),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(3, 4, 10),  # z should be ignored in Phase 1
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 2400000000.0)
    assert abs(link.distance_m - 5.0) < 0.01


def test_rx_power_calculation():
    """Test received power calculation."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(0, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(10, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 2400000000.0)

    # rx_power = tx_power + tx_gain + rx_gain - path_loss
    expected_rx_power = 10.0 + 2.0 + 2.0 - link.path_loss_db
    assert abs(link.rx_power_dbm - expected_rx_power) < 0.01


def test_link_viability():
    """Test link viability determination."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    # Close devices should have viable link
    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(0, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(5, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 2400000000.0)
    assert link.link_viable is True
    assert link.link_margin_db > 0


def test_link_margin():
    """Test link margin calculation."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)
    building = create_simple_building()
    profile = create_simple_radio_profile()

    tx_device = Device(
        id='tx',
        device_type=DeviceType.SENSOR,
        position=Point3D(0, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )
    rx_device = Device(
        id='rx',
        device_type=DeviceType.SENSOR,
        position=Point3D(5, 0, 1.5),
        room_id='room_0',
        wall_id='wall_west',
        radio_profile=profile,
    )

    link = model.compute_link(tx_device, rx_device, building, {}, 2400000000.0)
    expected_margin = link.rx_power_dbm - profile.rx_sensitivity_dbm
    assert abs(link.link_margin_db - expected_margin) < 0.01
