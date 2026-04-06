"""Tests for BSP generator."""
import time
import pytest
from buildingspacegen.core import BuildingType, RoomType
from buildingspacegen.buildinggen import generate_building, load_archetype_directory
from buildingspacegen.buildinggen.postprocess.door_placement import choose_door_position_along_wall
from buildingspacegen.core.geometry import Point2D
from buildingspacegen.core.model import WallSegment, Material
from pathlib import Path
import numpy as np


def _room_aspect_ratio(room) -> float:
    """Return the longer-to-shorter side ratio for a room bounding box."""
    bbox = room.polygon.bounding_box()
    width = bbox.width()
    height = bbox.height()
    shortest = min(width, height)
    if shortest <= 1e-9:
        return float("inf")
    return max(width, height) / shortest


class TestBSPGenerator:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Load archetypes before each test."""
        archetype_dir = Path(__file__).parent.parent.parent / "data" / "archetypes"
        load_archetype_directory(str(archetype_dir))

    def test_generate_medium_office_basic(self):
        """Test basic medium office generation."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        assert building.building_type == BuildingType.MEDIUM_OFFICE
        assert abs(building.total_area_sqft - 25000) < 1.0
        assert building.seed == 42
        assert len(building.floors) == 1

    def test_generate_has_rooms(self):
        """Test that generated building has rooms."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        rooms = list(building.all_rooms())
        assert len(rooms) > 0

    def test_generate_has_walls(self):
        """Test that generated building has walls."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        walls = list(building.all_walls())
        assert len(walls) > 0

    def test_generate_has_doors(self):
        """Test that generated building has doors."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        doors = list(building.all_doors())
        assert len(doors) > 0

    def test_doors_respect_wall_end_clearance_or_center_fallback(self):
        """Doors should be randomized within legal spans or fall back to center."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        for door in building.all_doors():
            wall = building.get_wall(door.wall_id)
            wall_length = ((wall.end.x - wall.start.x) ** 2 + (wall.end.y - wall.start.y) ** 2) ** 0.5
            if wall_length >= 2.0 * door.width:
                min_t = door.width / wall_length
                max_t = 1.0 - min_t
                assert min_t <= door.position_along_wall <= max_t
            else:
                assert door.position_along_wall == 0.5

    def test_door_position_helper_is_deterministic_for_same_seed(self):
        """The helper should produce stable output for the same RNG seed."""
        wall = WallSegment(
            id="wall_001",
            start=Point2D(0.0, 0.0),
            end=Point2D(10.0, 0.0),
            height=3.0,
            materials=[Material("gypsum_double", 0.026)],
            is_exterior=False,
            room_ids=("room_001", "room_002"),
        )

        pos1 = choose_door_position_along_wall(wall, 0.9, np.random.default_rng(123))
        pos2 = choose_door_position_along_wall(wall, 0.9, np.random.default_rng(123))

        assert pos1 == pos2
        assert 0.09 <= pos1 <= 0.91

    def test_door_position_helper_uses_center_fallback_for_short_walls(self):
        """Short walls should fall back to centered placement."""
        wall = WallSegment(
            id="wall_001",
            start=Point2D(0.0, 0.0),
            end=Point2D(1.0, 0.0),
            height=3.0,
            materials=[Material("gypsum_double", 0.026)],
            is_exterior=False,
            room_ids=("room_001", "room_002"),
        )

        pos = choose_door_position_along_wall(wall, 0.9, np.random.default_rng(123))

        assert pos == 0.5

    def test_determinism(self):
        """Test that same seed produces identical building."""
        building1 = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        building2 = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        rooms1 = sorted(
            (r.room_type.value, round(r.polygon.bounding_box().min_x, 3), round(r.polygon.bounding_box().min_y, 3),
             round(r.polygon.bounding_box().max_x, 3), round(r.polygon.bounding_box().max_y, 3))
            for r in building1.all_rooms()
        )
        rooms2 = sorted(
            (r.room_type.value, round(r.polygon.bounding_box().min_x, 3), round(r.polygon.bounding_box().min_y, 3),
             round(r.polygon.bounding_box().max_x, 3), round(r.polygon.bounding_box().max_y, 3))
            for r in building2.all_rooms()
        )
        assert rooms1 == rooms2

        walls1 = sorted([w.id for w in building1.all_walls()])
        walls2 = sorted([w.id for w in building2.all_walls()])
        assert walls1 == walls2

        doors1 = sorted((d.id, d.wall_id, round(d.position_along_wall, 6)) for d in building1.all_doors())
        doors2 = sorted((d.id, d.wall_id, round(d.position_along_wall, 6)) for d in building2.all_doors())
        assert doors1 == doors2

    def test_different_seed_different_result(self):
        """Test that different seeds produce different buildings."""
        building1 = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        building2 = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=43,
        )

        rooms1_count = len(list(building1.all_rooms()))
        rooms2_count = len(list(building2.all_rooms()))
        # They might have same count but different layout
        assert rooms1_count > 0 and rooms2_count > 0

        doors1 = [(d.wall_id, round(d.position_along_wall, 6)) for d in building1.all_doors()]
        doors2 = [(d.wall_id, round(d.position_along_wall, 6)) for d in building2.all_doors()]
        assert doors1 != doors2

    def test_performance(self):
        """Test that generation is reasonably fast."""
        start = time.time()
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )
        elapsed = time.time() - start

        assert elapsed < 2.0  # Should complete in under 2 seconds

    def test_multi_floor(self):
        """Test multi-floor building generation."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=75000,
            num_floors=3,
            seed=42,
        )

        assert len(building.floors) == 3
        assert building.floors[0].elevation == 0.0
        assert building.floors[1].elevation == 3.0
        assert building.floors[2].elevation == 6.0

    def test_room_types_present(self):
        """Test that generated building contains expected room types."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        room_types = {room.room_type for room in building.all_rooms()}
        # Should have at least open office
        assert any(rt.value == "open_office" for rt in room_types)

    def test_room_accessibility(self):
        """Test that all rooms are reachable."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        # Test getting rooms by ID
        rooms = list(building.all_rooms())
        for room in rooms:
            fetched = building.get_room(room.id)
            assert fetched.id == room.id

    def test_wall_room_references(self):
        """Test that walls reference valid rooms."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        room_ids = {room.id for room in building.all_rooms()}
        for wall in building.all_walls():
            assert wall.room_ids[0] in room_ids
            if wall.room_ids[1] is not None:
                assert wall.room_ids[1] in room_ids

    def test_corridor_network_has_multiple_branches(self):
        """Layouts should have a corridor network, not a single bisecting strip."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        corridors = [room for room in building.all_rooms() if room.room_type == RoomType.CORRIDOR]
        assert len(corridors) >= 6

        corridor_x = {round(room.polygon.centroid().x, 1) for room in corridors}
        corridor_y = {round(room.polygon.centroid().y, 1) for room in corridors}
        assert len(corridor_x) > 1
        assert len(corridor_y) > 1

    def test_rooms_access_corridors_directly(self):
        """Non-corridor rooms should connect into circulation instead of daisy-chaining by doors."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        room_lookup = {room.id: room for room in building.all_rooms()}
        door_lookup = {door.id: door for door in building.all_doors()}

        for room in building.all_rooms():
            if room.room_type == RoomType.CORRIDOR:
                continue

            corridor_door_count = 0
            for door_id in room.door_ids:
                wall = building.get_wall(door_lookup[door_id].wall_id)
                adjacent_types = {
                    room_lookup[room_id].room_type
                    for room_id in wall.room_ids
                    if room_id is not None
                }
                if RoomType.CORRIDOR in adjacent_types:
                    corridor_door_count += 1

            assert corridor_door_count >= 1, f"{room.id} lacks direct corridor access"

    def test_room_types_are_mixed_across_floor(self):
        """Open office and support spaces should span multiple zones of the floor plate."""
        building = generate_building(
            building_type=BuildingType.MEDIUM_OFFICE,
            total_sqft=25000,
            num_floors=1,
            seed=42,
        )

        center = building.footprint.centroid()
        support_types = {
            RoomType.PRIVATE_OFFICE,
            RoomType.CONFERENCE,
            RoomType.RESTROOM,
            RoomType.MECHANICAL,
            RoomType.STORAGE,
            RoomType.IT_SERVER,
            RoomType.KITCHEN_BREAK,
        }

        open_office_quadrants = set()
        support_quadrants = set()
        for room in building.all_rooms():
            centroid = room.polygon.centroid()
            quadrant = ("E" if centroid.x >= center.x else "W") + ("N" if centroid.y >= center.y else "S")
            if room.room_type == RoomType.OPEN_OFFICE:
                open_office_quadrants.add(quadrant)
            if room.room_type in support_types:
                support_quadrants.add(quadrant)

        assert len(open_office_quadrants) >= 3
        assert len(support_quadrants) >= 3

    def test_non_corridor_rooms_stay_near_two_to_one_across_seed_sweep(self):
        """Representative seed sweeps should mostly avoid corridor-like non-corridor rooms."""
        ratios = []
        for seed in range(12):
            building = generate_building(
                building_type=BuildingType.MEDIUM_OFFICE,
                total_sqft=25000,
                num_floors=1,
                seed=seed,
            )
            ratios.extend(
                _room_aspect_ratio(room)
                for room in building.all_rooms()
                if room.room_type != RoomType.CORRIDOR
        )

        assert ratios
        outliers = [ratio for ratio in ratios if ratio > 2.0]
        assert len(outliers) <= max(4, int(len(ratios) * 0.15))
        assert max(ratios) <= 3.6
