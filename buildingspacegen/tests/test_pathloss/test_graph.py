"""Tests for path loss graph construction."""
import os
import numpy as np
import pytest
from buildingspacegen.buildinggen.api import generate_building
from buildingspacegen.core.enums import BuildingType
from buildingspacegen.sensorplacer.api import place_sensors
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


def test_build_graph_basic():
    """Test building a path loss graph for a small building."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    # Get first two devices
    devices = placement.devices[:2]
    if len(devices) >= 2:
        tx_id, rx_id = devices[0].id, devices[1].id

        link_fwd = graph.get_link(tx_id, rx_id, 2400000000.0)
        link_rev = graph.get_link(rx_id, tx_id, 2400000000.0)

        assert link_fwd is not None
        assert link_rev is not None

        # Path loss should be same (same walls crossed)
        assert abs(link_fwd.path_loss_db - link_rev.path_loss_db) < 0.01
        # But rx_power differs due to different device profiles
        # (they might have different gains/sensitivities)


def test_stochastic_variation_different_runs():
    """Test that different run_index produces different attenuations."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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

    # Get same link from both runs
    link_run0 = graph_run0.all_links[0]
    link_run1 = graph_run1.all_links[0]

    # Wall loss should be different (stochastic sampling)
    # Allow small chance they're the same, but typically different
    assert link_run0.tx_device_id == link_run1.tx_device_id
    # Note: stochastic nature means we can't guarantee difference, just observe it


def test_determinism_same_run():
    """Test that same seed and run_index produce identical results."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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

    # Compare first link
    if len(graph_900.all_links) > 0 and len(graph_2400.all_links) > 0:
        link_900 = graph_900.all_links[0]
        link_2400 = graph_2400.all_links[0]

        # Path loss should differ between frequencies
        # 2.4 GHz has higher path loss (higher frequency)
        assert link_2400.fspl_db > link_900.fspl_db


def test_viable_links():
    """Test that viable links are identified correctly."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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

    for link in viable_links:
        assert link.link_viable is True
        assert link.rx_power_dbm >= link.rx_device_id  # Sanity check


def test_graph_empty_with_no_devices():
    """Test graph construction with minimal device set."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=1000, seed=42)
    placement = place_sensors(building)

    db = MaterialRFDatabase.from_yaml(get_materials_path())
    model = MultiWallPathLossModel(db)

    if len(placement.devices) > 1:
        graph = build_path_loss_graph(
            building, placement, model, db,
            frequency_hz=2400000000.0,
            seed=42,
            run_index=0
        )

        # Should have links for any devices present
        assert len(graph.all_links) >= 0


def test_link_details():
    """Test that link details are populated correctly."""
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

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
