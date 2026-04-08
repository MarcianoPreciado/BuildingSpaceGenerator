"""Regression tests for the simulate command data flow."""
import json

from buildingspacegen.cli.main import SIMULATION_RADIO_SETTINGS, build_simulation_scene, run_single_simulation
from buildingspacegen.core.enums import BuildingType, DeviceType
from buildingspacegen.pipeline import (
    ExistingBuildingPipelineConfig,
    ImportedPipelineConfig,
    PipelineConfig,
    run_existing_building_pipeline,
    run_imported_pipeline,
    run_pipeline,
)


def test_run_single_simulation_keeps_both_frequency_bands():
    config = PipelineConfig(
        building_type=BuildingType.MEDIUM_OFFICE,
        total_sqft=10000,
        seed=11,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)

    simulated = run_single_simulation(result)
    scene = simulated.to_json()

    frequencies = {link["frequency_hz"] for link in scene["links"]}
    assert frequencies == {900000000.0, 2400000000.0}


def test_run_single_simulation_has_controller_link_for_every_sensor():
    config = PipelineConfig(
        building_type=BuildingType.MEDIUM_OFFICE,
        total_sqft=10000,
        seed=11,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)

    simulated = run_single_simulation(result)
    controllers = {
        device.id
        for device in simulated.placement.devices
        if device.device_type in {DeviceType.MAIN_CONTROLLER, DeviceType.SECONDARY_CONTROLLER}
    }
    sensors = [
        device.id
        for device in simulated.placement.devices
        if device.device_type == DeviceType.SENSOR
    ]

    for freq, graph in simulated.path_loss_graphs.items():
        for sensor_id in sensors:
            assert any(
                (
                    link.tx_device_id == sensor_id and link.rx_device_id in controllers
                ) or (
                    link.rx_device_id == sensor_id and link.tx_device_id in controllers
                )
                for link in graph.all_links
            ), f"Missing controller link for sensor {sensor_id} at {freq}"


def test_run_single_simulation_emits_one_link_per_sensor_per_band():
    config = PipelineConfig(
        building_type=BuildingType.MEDIUM_OFFICE,
        total_sqft=10000,
        seed=11,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)

    simulated = run_single_simulation(result)
    sensor_count = sum(
        1 for device in simulated.placement.devices if device.device_type == DeviceType.SENSOR
    )

    for graph in simulated.path_loss_graphs.values():
        assert len(graph.all_links) == sensor_count


def test_run_single_simulation_sensor_metadata_matches_viable_bands():
    config = PipelineConfig(
        building_type=BuildingType.MEDIUM_OFFICE,
        total_sqft=10000,
        seed=11,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)

    simulated = run_single_simulation(result)
    controllers = {
        device.id
        for device in simulated.placement.devices
        if device.device_type in {DeviceType.MAIN_CONTROLLER, DeviceType.SECONDARY_CONTROLLER}
    }

    for sensor in [device for device in simulated.placement.devices if device.device_type == DeviceType.SENSOR]:
        viable_bands = sorted(
            freq
            for freq, graph in simulated.path_loss_graphs.items()
            if any(
                link.link_viable and (
                    (link.tx_device_id == sensor.id and link.rx_device_id in controllers) or
                    (link.rx_device_id == sensor.id and link.tx_device_id in controllers)
                )
                for link in graph.all_links
            )
        )
        assert sensor.metadata["viable_controller_link_frequencies_hz"] == viable_bands
        assert sensor.metadata["has_viable_controller_link"] == bool(viable_bands)


def test_build_simulation_scene_includes_band_settings():
    config = PipelineConfig(
        building_type=BuildingType.MEDIUM_OFFICE,
        total_sqft=10000,
        seed=11,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)

    scene = build_simulation_scene(run_single_simulation(result))

    assert scene["simulation"]["mode"] == "single_run"
    assert scene["simulation"]["per_frequency"] == {
        str(int(freq_hz)): settings
        for freq_hz, settings in SIMULATION_RADIO_SETTINGS.items()
    }


def test_imported_run_single_simulation_emits_devices_and_band_links():
    result = run_imported_pipeline(
        ImportedPipelineConfig(
            graph_path="Sample Buildings/Millrock Office.graph.json",
            floor_selector="Floor 1",
            seed=42,
            frequencies_hz=[900e6, 2.4e9],
        )
    )

    simulated = run_single_simulation(result)
    scene = build_simulation_scene(simulated)

    assert len(scene["devices"]) > 0
    assert scene["simulation"]["mode"] == "single_run"
    frequencies = {link["frequency_hz"] for link in scene["links"]}
    assert frequencies == {900000000.0, 2400000000.0}


def test_existing_building_pipeline_rehydrates_building_only_scene(tmp_path):
    imported = run_imported_pipeline(
        ImportedPipelineConfig(
            graph_path="Sample Buildings/Millrock Office.graph.json",
            floor_selector="Floor 1",
            seed=42,
            frequencies_hz=[900e6, 2.4e9],
        )
    )
    building_only_scene = {"building": imported.to_json()["building"], "devices": None, "radio_profiles": None, "links": None, "simulation": None}
    input_path = tmp_path / "millrock-building-only.json"
    input_path.write_text(json.dumps(building_only_scene))

    result = run_existing_building_pipeline(
        ExistingBuildingPipelineConfig(
            input_path=str(input_path),
            seed=42,
            frequencies_hz=[900e6, 2.4e9],
        )
    )

    simulated = build_simulation_scene(run_single_simulation(result))
    assert len(simulated["devices"]) > 0
    frequencies = {link["frequency_hz"] for link in simulated["links"]}
    assert frequencies == {900000000.0, 2400000000.0}
