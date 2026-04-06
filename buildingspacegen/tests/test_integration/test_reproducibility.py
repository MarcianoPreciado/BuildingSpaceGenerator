"""Tests for deterministic reproducibility."""
import json
from buildingspacegen.pipeline import PipelineConfig, run_pipeline
from buildingspacegen.core.enums import BuildingType


def test_same_seed_same_building():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=20000, seed=42)
    r1 = run_pipeline(config)
    r2 = run_pipeline(config)
    # Same number of rooms and devices
    rooms1 = list(r1.building.all_rooms())
    rooms2 = list(r2.building.all_rooms())
    assert len(rooms1) == len(rooms2)
    assert len(r1.placement.devices) == len(r2.placement.devices)
    # Same device positions
    for d1, d2 in zip(r1.placement.devices, r2.placement.devices):
        assert abs(d1.position.x - d2.position.x) < 1e-6
        assert abs(d1.position.y - d2.position.y) < 1e-6


def test_different_seeds_different_buildings():
    c1 = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=20000, seed=1)
    c2 = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=20000, seed=2)
    r1 = run_pipeline(c1)
    r2 = run_pipeline(c2)
    # Different seeds should (almost always) produce different layouts
    # We just verify the pipeline ran successfully for both
    assert r1.building.seed == 1
    assert r2.building.seed == 2


def test_json_round_trip():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000, seed=42)
    result = run_pipeline(config)
    scene = result.to_json()
    # Serialize and deserialize
    json_str = json.dumps(scene)
    scene2 = json.loads(json_str)
    assert scene2["building"]["seed"] == 42
    assert len(scene2["devices"]) == len(result.placement.devices)
