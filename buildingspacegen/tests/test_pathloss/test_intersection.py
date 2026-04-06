"""Tests for ray-wall intersection geometry."""
import pytest
from buildingspacegen.core.geometry import Point2D, Polygon2D
from buildingspacegen.core.model import Building, Floor, Room, WallSegment, Door, Material
from buildingspacegen.core.enums import BuildingType, RoomType
from buildingspacegen.pathloss.geometry import find_intersected_walls


def create_two_room_building():
    """Create a building with two rooms separated by an interior wall."""
    # Two rooms separated by a vertical wall at x=10
    room_0_polygon = Polygon2D([
        Point2D(0, 0),
        Point2D(10, 0),
        Point2D(10, 20),
        Point2D(0, 20),
    ])

    room_1_polygon = Polygon2D([
        Point2D(10, 0),
        Point2D(20, 0),
        Point2D(20, 20),
        Point2D(10, 20),
    ])

    # Interior wall separating the two rooms
    wall_interior = WallSegment(
        id='wall_interior',
        start=Point2D(10, 0),
        end=Point2D(10, 20),
        height=3.0,
        materials=[Material('gypsum_double', 0.026)],
        is_exterior=False,
        room_ids=('room_0', 'room_1'),
    )

    # Exterior walls
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
        polygon=room_0_polygon,
        floor_index=0,
        wall_ids=['wall_left', 'wall_interior', 'wall_bottom', 'wall_top'],
        door_ids=[],
        ceiling_height=3.0,
    )

    room_1 = Room(
        id='room_1',
        room_type=RoomType.OPEN_OFFICE,
        polygon=room_1_polygon,
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
        footprint=Polygon2D([
            Point2D(0, 0),
            Point2D(20, 0),
            Point2D(20, 20),
            Point2D(0, 20),
        ]),
    )

    building = Building(
        building_type=BuildingType.MEDIUM_OFFICE,
        floors=[floor],
        footprint=floor.footprint,
        total_area_sqft=400 * 10.764,
        seed=42,
    )

    return building


def test_no_wall_intersection():
    """Test ray with no wall intersections."""
    building = create_two_room_building()

    # Ray within room 0, parallel to interior wall, doesn't cross
    tx_pos = Point2D(2, 10)
    rx_pos = Point2D(8, 10)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    assert len(intersections) == 0


def test_single_wall_intersection():
    """Test ray crossing a single interior wall."""
    building = create_two_room_building()

    # Ray crossing from room 0 to room 1
    tx_pos = Point2D(5, 10)
    rx_pos = Point2D(15, 10)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    assert len(intersections) == 1
    assert intersections[0]['wall_id'] == 'wall_interior'
    assert intersections[0]['material'] == 'gypsum_double'
    assert intersections[0]['is_door'] is False


def test_parallel_ray_no_intersection():
    """Test ray parallel to a wall doesn't intersect."""
    building = create_two_room_building()

    # Ray parallel to interior wall
    tx_pos = Point2D(5, 5)
    rx_pos = Point2D(5, 15)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    # Should not intersect with interior wall (parallel)
    interior_wall_hits = [i for i in intersections if i['wall_id'] == 'wall_interior']
    assert len(interior_wall_hits) == 0


def test_diagonal_ray_multiple_walls():
    """Test diagonal ray crossing multiple walls."""
    building = create_two_room_building()

    # Diagonal from corner of room 0 to corner of room 1
    tx_pos = Point2D(0, 0)
    rx_pos = Point2D(20, 20)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    # Should cross interior wall and potentially exterior walls
    assert len(intersections) > 0
    interior_hits = [i for i in intersections if i['wall_id'] == 'wall_interior']
    assert len(interior_hits) > 0


def test_wall_material_lookup():
    """Test that wall materials are correctly identified."""
    building = create_two_room_building()

    tx_pos = Point2D(5, 10)
    rx_pos = Point2D(15, 10)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    assert len(intersections) == 1
    assert intersections[0]['material'] == 'gypsum_double'


def test_ray_endpoint_on_wall():
    """Test ray with endpoint exactly on a wall."""
    building = create_two_room_building()

    # Ray starting on interior wall
    tx_pos = Point2D(10, 10)
    rx_pos = Point2D(15, 10)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    # Should intersect at the starting point
    assert len(intersections) > 0


def test_no_intersection_parallel_ray_offset():
    """Test parallel ray offset from wall."""
    building = create_two_room_building()

    # Parallel ray on left side, doesn't cross interior wall
    tx_pos = Point2D(2, 5)
    rx_pos = Point2D(2, 15)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    interior_hits = [i for i in intersections if i['wall_id'] == 'wall_interior']
    assert len(interior_hits) == 0


def test_crossing_interior_wall():
    """Test ray crossing the interior wall between rooms."""
    building = create_two_room_building()

    # Long diagonal crosses the shared interior wall once.
    tx_pos = Point2D(2, 2)
    rx_pos = Point2D(18, 18)

    intersections = find_intersected_walls(tx_pos, rx_pos, building)
    assert len(intersections) == 1
    assert intersections[0]['wall_id'] == 'wall_interior'


def test_intersection_consistency():
    """Test that intersection direction doesn't matter (symmetry)."""
    building = create_two_room_building()

    tx_pos = Point2D(5, 10)
    rx_pos = Point2D(15, 10)

    # Forward direction
    intersections_fwd = find_intersected_walls(tx_pos, rx_pos, building)

    # Reverse direction
    intersections_rev = find_intersected_walls(rx_pos, tx_pos, building)

    assert len(intersections_fwd) == len(intersections_rev)
    assert set(i['wall_id'] for i in intersections_fwd) == set(i['wall_id'] for i in intersections_rev)
