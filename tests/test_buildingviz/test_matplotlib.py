"""Tests for matplotlib 2D renderer."""
import pytest
import matplotlib.pyplot as plt

from buildingspacegen.core.geometry import Point2D, Polygon2D
from buildingspacegen.core.model import Building, Floor
from buildingspacegen.core.enums import BuildingType, RoomType, WallMaterial
from buildingspacegen.buildingviz.renderers.matplotlib_2d import render_building_2d


def test_render_simple_building():
    """Test rendering a minimal building."""
    # Create a simple building
    footprint = Polygon2D([Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)])
    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[],
        footprint=footprint,
        total_area_sqft=1000,
        seed=42,
    )

    # Should not crash even with no floors
    fig = render_building_2d(building, save_path=None)
    assert fig is not None
    plt.close(fig)


def test_render_building_with_rooms():
    """Test rendering a building with rooms and walls."""
    from buildingspacegen.core.model import Room, Floor, WallSegment, Material

    footprint = Polygon2D([
        Point2D(0, 0), Point2D(20, 0), Point2D(20, 20), Point2D(0, 20)
    ])

    room_poly = Polygon2D([
        Point2D(2, 2), Point2D(18, 2), Point2D(18, 18), Point2D(2, 18)
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

    wall = WallSegment(
        id="wall_001",
        start=Point2D(0, 0),
        end=Point2D(20, 0),
        height=3.0,
        materials=[Material(name="gypsum_double", thickness_m=0.026)],
        is_exterior=True,
        room_ids=("room_001", None),
    )

    floor = Floor(
        index=0,
        elevation=0.0,
        footprint=footprint,
        rooms=[room],
        walls=[wall],
        doors=[],
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=1000,
        seed=42,
    )

    fig = render_building_2d(building, show_room_labels=True, save_path=None)
    assert fig is not None
    plt.close(fig)


def test_render_building_with_devices():
    """Test rendering a building with devices."""
    from buildingspacegen.core.model import Room, Floor, WallSegment, Material
    from buildingspacegen.core.device import Device, DevicePlacement, PlacementRules, RadioProfile
    from buildingspacegen.core.geometry import Point3D
    from buildingspacegen.core.enums import DeviceType

    footprint = Polygon2D([
        Point2D(0, 0), Point2D(20, 0), Point2D(20, 20), Point2D(0, 20)
    ])

    room_poly = Polygon2D([
        Point2D(2, 2), Point2D(18, 2), Point2D(18, 18), Point2D(2, 18)
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
        elevation=0.0,
        footprint=footprint,
        rooms=[room],
        walls=[],
        doors=[],
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=1000,
        seed=42,
    )

    # Create devices
    profile = RadioProfile(
        name="test_profile",
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=5.0,
        rx_antenna_gain_dbi=5.0,
        rx_sensitivity_dbm=-100.0,
        supported_frequencies_hz=[900e6, 2.4e9],
    )

    devices = DevicePlacement(
        building_seed=42,
        devices=[
            Device(
                id="dev_001",
                device_type=DeviceType.MAIN_CONTROLLER,
                position=Point3D(10.0, 10.0, 2.5),
                room_id="room_001",
                wall_id="",
                radio_profile=profile,
            ),
            Device(
                id="dev_002",
                device_type=DeviceType.SENSOR,
                position=Point3D(5.0, 5.0, 1.5),
                room_id="room_001",
                wall_id="",
                radio_profile=profile,
            ),
        ],
        placement_rules=PlacementRules(
            main_controller_per_sqft=0.0,
            main_controller_wall_height_m=2.5,
            main_controller_prefer_center=True,
            secondary_controller_per_sqft=0.0,
            secondary_controller_wall_height_m=2.0,
            sensor_min_per_room=1,
            sensor_per_sqft=0.0,
            sensor_wall_height_m=1.5,
            sensor_min_spacing_m=3.0,
        ),
    )

    fig = render_building_2d(building, devices=devices, save_path=None)
    assert fig is not None
    plt.close(fig)


def test_render_building_with_links():
    """Test rendering a building with RF links."""
    from buildingspacegen.core.model import Room, Floor
    from buildingspacegen.core.device import Device, DevicePlacement, PlacementRules, RadioProfile
    from buildingspacegen.core.geometry import Point3D
    from buildingspacegen.core.enums import DeviceType
    from buildingspacegen.core.links import PathLossGraph, LinkResult

    footprint = Polygon2D([
        Point2D(0, 0), Point2D(20, 0), Point2D(20, 20), Point2D(0, 20)
    ])

    room_poly = Polygon2D([
        Point2D(2, 2), Point2D(18, 2), Point2D(18, 18), Point2D(2, 18)
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
        elevation=0.0,
        footprint=footprint,
        rooms=[room],
        walls=[],
        doors=[],
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=1000,
        seed=42,
    )

    profile = RadioProfile(
        name="test_profile",
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=5.0,
        rx_antenna_gain_dbi=5.0,
        rx_sensitivity_dbm=-100.0,
        supported_frequencies_hz=[900e6],
    )

    devices = DevicePlacement(
        building_seed=42,
        devices=[
            Device(
                id="dev_001",
                device_type=DeviceType.MAIN_CONTROLLER,
                position=Point3D(10.0, 10.0, 2.5),
                room_id="room_001",
                wall_id="",
                radio_profile=profile,
            ),
            Device(
                id="dev_002",
                device_type=DeviceType.SENSOR,
                position=Point3D(5.0, 5.0, 1.5),
                room_id="room_001",
                wall_id="",
                radio_profile=profile,
            ),
        ],
        placement_rules=PlacementRules(
            main_controller_per_sqft=0.0,
            main_controller_wall_height_m=2.5,
            main_controller_prefer_center=True,
            secondary_controller_per_sqft=0.0,
            secondary_controller_wall_height_m=2.0,
            sensor_min_per_room=1,
            sensor_per_sqft=0.0,
            sensor_wall_height_m=1.5,
            sensor_min_spacing_m=3.0,
        ),
    )

    # Create path loss graph
    links = PathLossGraph()
    links.add_link(LinkResult(
        tx_device_id="dev_001",
        rx_device_id="dev_002",
        frequency_hz=900e6,
        distance_m=7.07,
        fspl_db=50.9,
        wall_loss_db=0.0,
        path_loss_db=50.9,
        rx_power_dbm=-40.9,
        walls_crossed=0,
        link_viable=True,
        link_margin_db=59.1,
    ))

    fig = render_building_2d(
        building,
        devices=devices,
        links=links,
        frequency_hz=900e6,
        save_path=None
    )
    assert fig is not None
    plt.close(fig)


def test_render_to_file(tmp_path):
    """Test rendering and saving to file."""
    from buildingspacegen.core.model import Room, Floor

    footprint = Polygon2D([
        Point2D(0, 0), Point2D(10, 0), Point2D(10, 10), Point2D(0, 10)
    ])

    room_poly = Polygon2D([
        Point2D(1, 1), Point2D(9, 1), Point2D(9, 9), Point2D(1, 9)
    ])

    room = Room(
        id="room_001",
        room_type=RoomType.CONFERENCE,
        polygon=room_poly,
        floor_index=0,
        wall_ids=[],
        door_ids=[],
        ceiling_height=3.0,
    )

    floor = Floor(
        index=0,
        elevation=0.0,
        footprint=footprint,
        rooms=[room],
        walls=[],
        doors=[],
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=500,
        seed=42,
    )

    output_path = tmp_path / "test_render.png"
    fig = render_building_2d(building, save_path=str(output_path))
    assert fig is not None
    assert output_path.exists()
    plt.close(fig)
