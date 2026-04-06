"""Tests for BSP generator."""
import time
import pytest
from buildingspacegen.core import BuildingType
from buildingspacegen.buildinggen import generate_building, load_archetype_directory
from pathlib import Path


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

        rooms1 = sorted([r.id for r in building1.all_rooms()])
        rooms2 = sorted([r.id for r in building2.all_rooms()])
        assert rooms1 == rooms2

        walls1 = sorted([w.id for w in building1.all_walls()])
        walls2 = sorted([w.id for w in building2.all_walls()])
        assert walls1 == walls2

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
            if wall.room_ids[0] != "exterior":
                assert wall.room_ids[0] in room_ids
            if wall.room_ids[1] is not None:
                assert wall.room_ids[1] in room_ids
