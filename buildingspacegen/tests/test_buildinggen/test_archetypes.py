"""Tests for archetypes."""
import pytest
from pathlib import Path
from buildingspacegen.buildinggen import (
    Archetype, ArchetypeRegistry, get_default_registry, load_archetype_directory
)


class TestArchetype:
    def test_load_medium_office(self):
        """Test loading medium office archetype."""
        archetype_path = (
            Path(__file__).parent.parent.parent / "data" / "archetypes" / "medium_office.yaml"
        )
        archetype = Archetype.from_yaml_file(str(archetype_path))

        assert archetype.building_type_str == "medium_office"
        assert archetype.floor_ceiling_height_m == 3.0
        assert archetype.floor_corridor_width_m == 1.8
        assert len(archetype.room_program) > 0

    def test_room_program_fractions_sum_to_one(self):
        """Test that room program fractions sum to ~1.0."""
        archetype_path = (
            Path(__file__).parent.parent.parent / "data" / "archetypes" / "medium_office.yaml"
        )
        archetype = Archetype.from_yaml_file(str(archetype_path))

        total_fraction = sum(rp.area_fraction for rp in archetype.room_program)
        assert 0.95 <= total_fraction <= 1.05  # Within 5% tolerance

    def test_archetype_validation(self):
        """Test archetype validation."""
        archetype_path = (
            Path(__file__).parent.parent.parent / "data" / "archetypes" / "medium_office.yaml"
        )
        archetype = Archetype.from_yaml_file(str(archetype_path))

        # Should not raise
        archetype.validate()

    def test_load_all_archetypes(self):
        """Test loading all archetype files."""
        archetype_dir = Path(__file__).parent.parent.parent / "data" / "archetypes"
        expected_files = ["medium_office.yaml", "large_office.yaml", "warehouse.yaml"]

        for expected_file in expected_files:
            path = archetype_dir / expected_file
            assert path.exists(), f"{expected_file} not found"
            archetype = Archetype.from_yaml_file(str(path))
            archetype.validate()


class TestArchetypeRegistry:
    def test_registry_register_and_get(self):
        """Test registering and getting archetypes."""
        archetype_path = (
            Path(__file__).parent.parent.parent / "data" / "archetypes" / "medium_office.yaml"
        )
        archetype = Archetype.from_yaml_file(str(archetype_path))

        registry = ArchetypeRegistry()
        registry.register("medium_office", archetype)
        fetched = registry.get("medium_office")

        assert fetched.building_type_str == "medium_office"

    def test_registry_not_found(self):
        """Test retrieving non-existent archetype raises error."""
        registry = ArchetypeRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_load_from_directory(self):
        """Test loading all archetypes from directory."""
        archetype_dir = Path(__file__).parent.parent.parent / "data" / "archetypes"
        registry = ArchetypeRegistry()
        registry.load_from_directory(str(archetype_dir))

        # Should have loaded 3 archetypes
        assert registry.get("medium_office") is not None
        assert registry.get("large_office") is not None
        assert registry.get("warehouse") is not None

    def test_default_registry(self):
        """Test default registry instance."""
        registry = get_default_registry()
        assert registry is not None


class TestArchetypeProperties:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Load archetypes before each test."""
        archetype_dir = Path(__file__).parent.parent.parent / "data" / "archetypes"
        load_archetype_directory(str(archetype_dir))

    def test_medium_office_properties(self):
        """Test medium office specific properties."""
        registry = get_default_registry()
        archetype = registry.get("medium_office")

        assert 1.2 <= archetype.footprint_aspect_ratio_min <= 1.5
        assert archetype.footprint_aspect_ratio_max >= 2.0
        assert archetype.wall_exterior == "reinforced_concrete"

    def test_large_office_properties(self):
        """Test large office specific properties."""
        registry = get_default_registry()
        archetype = registry.get("large_office")

        assert archetype.floor_corridor_width_m == 2.0
        # Open office should be larger fraction
        open_office_fraction = next(
            (rp.area_fraction for rp in archetype.room_program if rp.room_type.value == "open_office"),
            0
        )
        assert open_office_fraction >= 0.5

    def test_warehouse_properties(self):
        """Test warehouse specific properties."""
        registry = get_default_registry()
        archetype = registry.get("warehouse")

        # Warehouse should have 8m ceiling
        warehouse_bay_metadata = next(
            (rp for rp in archetype.room_program if rp.room_type.value == "warehouse_bay"),
            None
        )
        assert warehouse_bay_metadata is not None
        assert warehouse_bay_metadata.area_fraction >= 0.75
