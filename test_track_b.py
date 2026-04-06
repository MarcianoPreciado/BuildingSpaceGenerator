#!/usr/bin/env python3
"""Integration test for Track B implementation."""
import sys
import os

# Add buildingspacegen to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'buildingspacegen'))

from buildingspacegen.core.enums import BuildingType, DeviceType
from buildingspacegen.buildinggen.api import generate_building, load_archetype_directory
from buildingspacegen.sensorplacer.api import place_sensors
from buildingspacegen.pathloss.materials import MaterialRFDatabase
from buildingspacegen.pathloss.models.multiwall import MultiWallPathLossModel
from buildingspacegen.pathloss.graph import build_path_loss_graph, build_path_loss_graphs
import numpy as np

# Load archetypes at module init
archetype_dir = os.path.join(os.path.dirname(__file__), 'buildingspacegen', 'data', 'archetypes')
load_archetype_directory(archetype_dir)

def test_material_database():
    """Test RF material database."""
    print("\n=== TEST: Material Database ===")
    db = MaterialRFDatabase.from_yaml('data/materials/rf_materials.yaml')
    print(f"Loaded {len(db.entries)} material entries")

    # Check we have all materials
    materials = set()
    for (mat_name, freq), _ in db.entries.items():
        materials.add(mat_name)

    expected = {
        'gypsum_single', 'gypsum_double', 'concrete_block', 'reinforced_concrete',
        'brick', 'glass_standard', 'glass_low_e', 'wood_door', 'metal_fire_door', 'elevator_shaft'
    }
    assert materials == expected, f"Missing materials: {expected - materials}"
    print(f"✓ All 10 materials present: {sorted(materials)}")

    # Check both frequency bands
    for mat in materials:
        for freq in [900000000.0, 2400000000.0]:
            assert (mat, freq) in db.entries, f"Missing {mat} at {freq}"
    print("✓ Both frequency bands (900 MHz, 2.4 GHz) present for all materials")

    # Test stochastic sampling
    rng = np.random.default_rng(42)
    samples = [db.get_attenuation('gypsum_double', 2400000000.0, rng) for _ in range(100)]
    mean_sample = np.mean(samples)
    mean_expected = db.get_deterministic_attenuation('gypsum_double', 2400000000.0)
    assert abs(mean_sample - mean_expected) < mean_expected * 0.2, "Mean attenuation mismatch"
    print(f"✓ Stochastic sampling works: mean={mean_sample:.2f} dB (expected ~{mean_expected:.2f} dB)")

    # Test frequency penetration
    for mat in ['gypsum_double', 'concrete_block']:
        a900 = db.get_deterministic_attenuation(mat, 900000000.0)
        a2400 = db.get_deterministic_attenuation(mat, 2400000000.0)
        assert a900 <= a2400, f"900 MHz should penetrate better than 2.4 GHz"
    print("✓ Lower frequency (900 MHz) has lower attenuation than higher frequency (2.4 GHz)")


def test_sensor_placement():
    """Test sensor placement."""
    print("\n=== TEST: Sensor Placement ===")

    # Generate a building
    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    print(f"Generated {BuildingType.MEDIUM_OFFICE.value} building: {building.total_area_sqft:.0f} sqft")
    print(f"  Floors: {len(building.floors)}")
    total_rooms = sum(len(f.rooms) for f in building.floors)
    print(f"  Rooms: {total_rooms}")
    total_walls = sum(len(f.walls) for f in building.floors)
    print(f"  Walls: {total_walls}")

    # Place sensors
    placement = place_sensors(building)
    print(f"Placed {len(placement.devices)} devices")

    main_controllers = placement.get_devices_by_type(DeviceType.MAIN_CONTROLLER)
    secondary_controllers = placement.get_devices_by_type(DeviceType.SECONDARY_CONTROLLER)
    sensors = placement.get_devices_by_type(DeviceType.SENSOR)

    print(f"  Main controllers: {len(main_controllers)}")
    print(f"  Secondary controllers: {len(secondary_controllers)}")
    print(f"  Sensors: {len(sensors)}")

    assert len(main_controllers) >= 1, "Should have at least 1 main controller"
    assert len(secondary_controllers) >= 1, "Should have at least 1 secondary controller"
    assert len(sensors) > 0, "Should have at least 1 sensor"
    print("✓ Device counts are reasonable")

    # Check all devices are on valid walls
    wall_ids = {w.id for w in building.all_walls()}
    for device in placement.devices:
        assert device.wall_id in wall_ids, f"Device {device.id} on invalid wall {device.wall_id}"
    print("✓ All devices are on valid walls")

    # Check devices are at correct heights
    from buildingspacegen.sensorplacer.rules import DEFAULT_RULES
    for device in placement.devices:
        if device.device_type == DeviceType.MAIN_CONTROLLER:
            assert abs(device.position.z - DEFAULT_RULES.main_controller_wall_height_m) < 0.01
        elif device.device_type == DeviceType.SECONDARY_CONTROLLER:
            assert abs(device.position.z - DEFAULT_RULES.secondary_controller_wall_height_m) < 0.01
        elif device.device_type == DeviceType.SENSOR:
            assert abs(device.position.z - DEFAULT_RULES.sensor_wall_height_m) < 0.01
    print("✓ All devices are at correct heights")

    # Test determinism
    building2 = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=50000, seed=42)
    placement2 = place_sensors(building2)
    assert len(placement.devices) == len(placement2.devices), "Determinism check failed"
    for d1, d2 in zip(placement.devices[:5], placement2.devices[:5]):
        assert d1.position.x == d2.position.x, "X coordinate not deterministic"
        assert d1.position.y == d2.position.y, "Y coordinate not deterministic"
    print("✓ Sensor placement is deterministic")


def test_path_loss_computation():
    """Test path loss computation."""
    print("\n=== TEST: Path Loss Computation ===")

    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

    db = MaterialRFDatabase.from_yaml('data/materials/rf_materials.yaml')
    model = MultiWallPathLossModel(db)

    # Compute graph for 2.4 GHz
    graph = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )

    n_devices = len(placement.devices)
    expected_links = n_devices * (n_devices - 1)
    print(f"Built path loss graph with {len(graph.all_links)} links (expected {expected_links})")
    assert len(graph.all_links) == expected_links, f"Link count mismatch"
    print("✓ All pairwise links computed")

    # Check link details
    link = graph.all_links[0]
    print(f"\nSample link ({link.tx_device_id} → {link.rx_device_id}):")
    print(f"  Distance: {link.distance_m:.2f} m")
    print(f"  FSPL: {link.fspl_db:.2f} dB")
    print(f"  Wall loss: {link.wall_loss_db:.2f} dB")
    print(f"  Path loss: {link.path_loss_db:.2f} dB")
    print(f"  RX power: {link.rx_power_dbm:.2f} dBm")
    print(f"  Walls crossed: {link.walls_crossed}")
    print(f"  Link viable: {link.link_viable}")
    print(f"  Link margin: {link.link_margin_db:.2f} dB")

    assert link.distance_m > 0, "Distance should be positive"
    assert link.fspl_db > 0, "FSPL should be positive"
    assert link.wall_loss_db >= 0, "Wall loss should be non-negative"
    assert link.path_loss_db > 0, "Path loss should be positive"
    print("✓ Link parameters are valid")

    # Test frequency-dependent behavior
    graph_900 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=900000000.0,
        seed=42,
        run_index=0
    )

    link_900 = graph_900.all_links[0]
    # 2.4 GHz should have higher FSPL than 900 MHz
    assert graph.all_links[0].fspl_db > link_900.fspl_db, "2.4 GHz FSPL should be higher"
    print(f"✓ Frequency-dependent FSPL: 900MHz={link_900.fspl_db:.1f} dB, 2.4GHz={graph.all_links[0].fspl_db:.1f} dB")

    # Test determinism
    graph2 = build_path_loss_graph(
        building, placement, model, db,
        frequency_hz=2400000000.0,
        seed=42,
        run_index=0
    )
    for l1, l2 in zip(
        sorted(graph.all_links, key=lambda l: (l.tx_device_id, l.rx_device_id))[:5],
        sorted(graph2.all_links, key=lambda l: (l.tx_device_id, l.rx_device_id))[:5]
    ):
        assert abs(l1.wall_loss_db - l2.wall_loss_db) < 1e-10, "Wall loss not deterministic"
    print("✓ Path loss computation is deterministic")


def test_multi_frequency():
    """Test multi-frequency graph building."""
    print("\n=== TEST: Multi-Frequency Graphs ===")

    building = generate_building(BuildingType.MEDIUM_OFFICE, total_sqft=10000, seed=42)
    placement = place_sensors(building)

    db = MaterialRFDatabase.from_yaml('data/materials/rf_materials.yaml')
    model = MultiWallPathLossModel(db)

    frequencies = [900000000.0, 2400000000.0]
    graphs = build_path_loss_graphs(
        building, placement, model, db,
        frequencies_hz=frequencies,
        seed=42,
        run_index=0
    )

    print(f"Built graphs for {len(graphs)} frequencies")
    assert 900000000.0 in graphs, "Missing 900 MHz graph"
    assert 2400000000.0 in graphs, "Missing 2.4 GHz graph"

    links_900 = graphs[900000000.0].all_links
    links_2400 = graphs[2400000000.0].all_links

    print(f"  900 MHz: {len(links_900)} links")
    print(f"  2.4 GHz: {len(links_2400)} links")

    assert len(links_900) == len(links_2400), "Same number of links expected"
    print("✓ Multi-frequency graphs built successfully")


def test_large_building():
    """Test with a larger building."""
    print("\n=== TEST: Large Building ===")

    building = generate_building(BuildingType.LARGE_OFFICE, total_sqft=250000, seed=42)
    placement = place_sensors(building)

    main_controllers = placement.get_devices_by_type(DeviceType.MAIN_CONTROLLER)
    secondary_controllers = placement.get_devices_by_type(DeviceType.SECONDARY_CONTROLLER)
    sensors = placement.get_devices_by_type(DeviceType.SENSOR)

    print(f"Large office building ({building.total_area_sqft:.0f} sqft):")
    print(f"  Main controllers: {len(main_controllers)}")
    print(f"  Secondary controllers: {len(secondary_controllers)}")
    print(f"  Sensors: {len(sensors)}")
    print(f"  Total devices: {len(placement.devices)}")

    assert len(main_controllers) > 1, "Large building should have multiple main controllers"
    assert len(sensors) > 100, "Large building should have many sensors"
    print("✓ Large building placement is reasonable")


def main():
    """Run all tests."""
    try:
        test_material_database()
        test_sensor_placement()
        test_path_loss_computation()
        test_multi_frequency()
        test_large_building()

        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
