"""Tests for path loss graph construction."""
import os
import pytest
from buildingspacegen.core.enums import BuildingType, DeviceType, RoomType
from buildingspacegen.core.geometry import Point2D, Point3D, Polygon2D
from buildingspacegen.core.model import Building, Floor, Room, WallSegment, Material
from buildingspacegen.core.device import Device, DevicePlacement, PlacementRules, RadioProfile
from buildingspacegen.pathloss.materials import MaterialRFDatabase
from buildingspacegen.pathloss.models.multiwall import MultiWallPathLossModel
from buildingspacegen.pathloss.graph import build_path_loss_graph, build_path_loss_graphs


def get_materials_path():
    """Get path to materials YAML file."""
    return os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..',
        'data', 'materials', 'rf_materials.yaml'
    )


def create_graph_test_building():
    """Create a small two-room building for path loss graph tests."""
    footprint = Polygon2D([
        Point2D(0, 0),
        Point2D(20, 0),
        Point2D(20, 20),
        Point2D(0, 20),
    ])

    wall_interior = WallSegment(
        id='wall_interior',
        start=Point2D(10, 0),
        end=Point2D(10, 20),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', 'room_1'),
    )
    wall_left = WallSegment(
        id='wall_left',
        start=Point2D(0, 0),
        end=Point2D(0, 20),
        height=3.0,
        materials=[Material('concrete_block', 0.2)],
        is_exterior=True,
        room_ids=('room_0', None),
    )
    wall_right = WallSegment(
        id='wall_right',
        start=Point2D(20, 20),
        end=Point2D(20, 0),
        height=3.0,
        materials=[Material('concrete_block', 0.2)],
        is_exterior=True,
        room_ids=('room_1', None),
    )
    wall_bottom = WallSegment(
        id='wall_bottom',
        start=Point2D(20, 0),
        end=Point2D(0, 0),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', 'room_1'),
    )
    wall_top = WallSegment(
        id='wall_top',
        start=Point2D(0, 20),
        end=Point2D(20, 20),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', 'room_1'),
    )

    room_0 = Room(
        id='room_0',
        room_type=RoomType.OPEN_OFFICE,
        polygon=Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 20),
            Point2D(0, 20),
        ]),
        floor_index=0,
        wall_ids=['wall_left', 'wall_interior', 'wall_bottom', 'wall_top'],
        door_ids=[],
        ceiling_height=3.0,
    )

    room_1 = Room(
        id='room_1',
        room_type=RoomType.OPEN_OFFICE,
        polygon=Polygon2D([
            Point2D(10, 0),
            Point2D(20, 0),
            Point2D(20, 20),
            Point2D(10, 20),
        ]),
        floor_index=0,
        wall_ids=['wall_interior', 'wall_right', 'wall_bottom', 'wall_top'],
        door_ids=[],
        ceiling_height=3.0,
    )

    floor = Floor(
        index=0,
        rooms=[room_0, room_1],
        walls=[wall_interior, wall_left, wall_right, wall_bottom, wall_top],
        doors=[],
        elevation=0.0,
        footprint=footprint,
    )

    return Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=400 * 10.764,
        seed=42,
    )


def create_graph_test_placement():
    """Create a deterministic placement with three devices."""
    profile = RadioProfile(
        name='test_profile',
        tx_power_dbm=10.0,
        tx_antenna_gain_dbi=2.0,
        rx_antenna_gain_dbi=2.0,
        rx_sensitivity_dbm=-95.0,
        supported_frequencies_hz=[900000000.0, 2400000000.0],
    )
    return DevicePlacement(
        building_seed=42,
        devices=[
            Device(
                id='dev_a',
                device_type=DeviceType.SENSOR,
                position=Point3D(2, 10, 1.5),
                room_id='room_0',
                wall_id='wall_left',
                radio_profile=profile,
            ),
            Device(
                id='dev_b',
                device_type=DeviceType.SENSOR,
                position=Point3D(8, 10, 1.5),
                room_id='room_0',
                wall_id='wall_left',
                radio_profile=profile,
            ),
            Device(
                id='dev_c',
                device_type=DeviceType.SENSOR,
                position=Point3D(15, 10, 1.5),
                room_id='room_1',
                wall_id='wall_right',
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


def test_build_graph_basic():
    """Test building a path loss graph for a small building."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    assert graph is not None
    assert len(graph.all_links) > 0


def test_all_device_pairs_have_links():
    """Verify all pairwise device links are computed."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    # For N devices, should have N*(N-1) directed links
    n_devices = len(placement.devices)
    expected_links = n_devices * (n_devices - 1)
    assert len(graph.all_links) == expected_links


def test_link_symmetry():
    """Test that path loss is symmetric for same wall crossings."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    link_fwd = graph.get_link('dev_a', 'dev_c', 2400000000.0)
    link_rev = graph.get_link('dev_c', 'dev_a', 2400000000.0)

    assert link_fwd is not None
    assert link_rev is not None

    # Path loss should be same (same walls crossed)
    assert abs(link_fwd.path_loss_db - link_rev.path_loss_db) < 0.01
    # But rx_power differs due to different device profiles
    # (they might have different gains/sensitivities)


def test_stochastic_variation_different_runs():
    """Test that different run_index produces different attenuations."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph_run0 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    graph_run1 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=1
    )

    link_run0 = graph_run0.get_link('dev_a', 'dev_c', 2400000000.0)
    link_run1 = graph_run1.get_link('dev_a', 'dev_c', 2400000000.0)

    assert link_run0 is not None
    assert link_run1 is not None
    assert link_run0.wall_loss_db != link_run1.wall_loss_db


def test_determinism_same_run():
    """Test that same seed and run_index produce identical results."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph_a = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    graph_b = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    # Same seed and run should produce identical results
    links_a = sorted(graph_a.all_links, key=lambda l: (l.tx_device_id, l.rx_device_id))
    links_b = sorted(graph_b.all_links, key=lambda l: (l.tx_device_id, l.rx_device_id))

    assert len(links_a) == len(links_b)

    for link_a, link_b in zip(links_a, links_b):
        assert link_a.tx_device_id == link_b.tx_device_id
        assert link_a.rx_device_id == link_b.rx_device_id
        assert abs(link_a.wall_loss_db - link_b.wall_loss_db) < 1e-10


def test_build_multiple_frequency_graphs():
    """Test building graphs for multiple frequencies."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    frequencies = [900000000.0, 2400000000.0]
    graphs = build_path_loss_graphs(
        building, placement, model, db,
        frequencies_hz=frequencies,
        seed=42,
        run_index=0
    )

    assert len(graphs) == 2
    assert 900000000.0 in graphs
    assert 2400000000.0 in graphs

    # Both should have same number of links
    links_900 = graphs[900000000.0].all_links
    links_2400 = graphs[2400000000.0].all_links
    assert len(links_900) == len(links_2400)


def test_frequency_dependent_attenuation():
    """Test that different frequencies have different path loss."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph_900 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=900000000.0,
        seed=42,
        run_index=0
    )

    graph_2400 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    link_900 = graph_900.get_link('dev_a', 'dev_b', 900000000.0)
    link_2400 = graph_2400.get_link('dev_a', 'dev_b', 2400000000.0)

    assert link_900 is not None
    assert link_2400 is not None

    # Path loss should differ between frequencies
    # 2.4 GHz has higher path loss (higher frequency)
    assert link_2400.fspl_db > link_900.fspl_db


def test_viable_links():
    """Test that viable links are identified correctly."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    viable_links = graph.get_viable_links(2400000000.0)
    assert len(viable_links) > 0

    device_by_id = {device.id: device for device in placement.devices}

    for link in viable_links:
        assert link.link_viable is True
        assert link.rx_power_dbm >= device_by_id[link.rx_device_id].radio_profile.rx_sensitivity_dbm


def test_graph_empty_with_no_devices():
    """Test graph construction with minimal device set."""
    building = create_graph_test_building()
    placement = DevicePlacement(
        building_seed=42,
        devices=[],
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

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    assert len(graph.all_links) == 0


def test_link_details():
    """Test that link details are populated correctly."""
    building = create_graph_test_building()
    placement = create_graph_test_placement()

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    for link in graph.all_links:
        assert link.tx_device_id
        assert link.rx_device_id
        assert link.frequency_hz == 2400000000.0
        assert link.distance_m > 0
        assert link.fspl_db > 0
        assert link.wall_loss_db >= 0
        assert link.path_loss_db > 0
        assert isinstance(link.link_viable, bool)
        assert link.walls_crossed >= 0
