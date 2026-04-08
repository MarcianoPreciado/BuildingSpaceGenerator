"""Integration tests for the full pipeline."""
import pytest
from buildingspacegen.pipeline import PipelineConfig, run_pipeline
from buildingspacegen.core.enums import BuildingType


@pytest.mark.parametrize("building_type,sqft", [
    (BuildingType.MEDIUM_OFFICE, 25000),
    (BuildingType.LARGE_OFFICE, 60000),
    (BuildingType.WAREHOUSE, 40000),
])
def test_pipeline_all_building_types(building_type, sqft):
    config = PipelineConfig(building_type=building_type, total_sqft=sqft, seed=42)
    result = run_pipeline(config)
    assert result.building is not None
    assert result.placement is not None
    assert len(result.path_loss_graphs) == 2  # 900 MHz and 2.4 GHz
    assert result.building.building_type == building_type


def test_pipeline_json_output():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000, seed=7)
    result = run_pipeline(config)
    scene = result.to_json()
    assert "building" in scene
    assert "devices" in scene
    assert "radio_profiles" in scene
    assert scene["building"]["building_type"] == "medium_office"
    assert len(scene["devices"]) > 0
    assert scene["links"] is not None

    frequencies = {link["frequency_hz"] for link in scene["links"]}
    assert frequencies == {900000000.0, 2400000000.0}


def test_pipeline_device_count_reasonable():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=25000, seed=42)
    result = run_pipeline(config)
    devices = result.placement.devices
    # 25000 sqft should yield at least 1 main controller, some secondary, many sensors
    from buildingspacegen.core.enums import DeviceType
    mc = [d for d in devices if d.device_type == DeviceType.MAIN_CONTROLLER]
    sensors = [d for d in devices if d.device_type == DeviceType.SENSOR]
    assert len(mc) >= 1
    assert len(sensors) >= 10  # reasonable for 25k sqft


def test_pipeline_graph_has_links():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000, seed=42)
    result = run_pipeline(config)
    for freq, graph in result.path_loss_graphs.items():
        assert len(graph.all_links) > 0


def test_pipeline_marks_sensor_controller_connectivity():
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000, seed=42)
    result = run_pipeline(config)

    sensors = [
        device for device in result.placement.devices
        if device.device_type.value == "sensor"
    ]

    assert sensors
    for sensor in sensors:
        assert "has_viable_controller_link" in sensor.metadata
        assert "viable_controller_link_frequencies_hz" in sensor.metadata
        assert isinstance(sensor.metadata["has_viable_controller_link"], bool)
        assert isinstance(sensor.metadata["viable_controller_link_frequencies_hz"], list)


def test_pipeline_save_load_json(tmp_path):
    config = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    result = run_pipeline(config)
    out = str(tmp_path / "test.json")
    result.save_json(out)
    import json
    with open(out) as f:
        data = json.load(f)
    assert "building" in data
    assert "devices" in data
