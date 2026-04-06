"""Tests for RF material database."""
import os
import numpy as np
import pytest
from buildingspacegen.pathloss.materials import MaterialRFDatabase


def get_materials_path():
    """Get path to materials YAML file."""
    return os.path.join(
        os.path.dirname(__file__),
        '..', '..', '..',
        'data', 'materials', 'rf_materials.yaml'
    )


def test_load_materials():
    """Test loading material database from YAML."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    assert db is not None
    assert len(db.entries) > 0


def test_all_materials_present():
    """Verify all 10 materials are present."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())

    expected_materials = [
        'gypsum_single',
        'gypsum_double',
        'concrete_block',
        'reinforced_concrete',
        'brick',
        'glass_standard',
        'glass_low_e',
        'wood_door',
        'metal_fire_door',
        'elevator_shaft',
    ]

    found_materials = set()
    for (mat_name, _), _ in db.entries.items():
        found_materials.add(mat_name)

    for mat in expected_materials:
        assert mat in found_materials, f"Material {mat} not found in database"


def test_both_frequency_bands():
    """Verify both 2.4 GHz and 900 MHz bands for each material."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())

    frequencies = [900000000.0, 2400000000.0]
    expected_materials = [
        'gypsum_single',
        'gypsum_double',
        'concrete_block',
        'reinforced_concrete',
        'brick',
        'glass_standard',
        'glass_low_e',
        'wood_door',
        'metal_fire_door',
        'elevator_shaft',
    ]

    for mat in expected_materials:
        for freq in frequencies:
            key = (mat, freq)
            assert key in db.entries, f"Material {mat} missing frequency {freq}"


def test_stochastic_sampling():
    """Verify stochastic sampling statistics."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    rng = np.random.default_rng(42)

    # Test a specific material (gypsum_double at 2.4 GHz)
    samples = []
    for _ in range(1000):
        atten = db.get_attenuation('gypsum_double', 2400000000.0, rng)
        samples.append(atten)

    samples = np.array(samples)
    mean_atten = float(db.get_deterministic_attenuation('gypsum_double', 2400000000.0))
    sigma = db.entries[('gypsum_double', 2400000000.0)].sigma_attenuation_db

    # Verify mean is close (within 10%)
    sample_mean = np.mean(samples)
    assert abs(sample_mean - mean_atten) < mean_atten * 0.1

    # Verify standard deviation
    sample_std = np.std(samples)
    assert abs(sample_std - sigma) < sigma * 0.2

    # Verify 99.7% within 3 sigma (should be mostly within bounds)
    below_lower = np.sum(samples < 0)
    assert below_lower < 5  # Very few samples should be < 0


def test_frequency_bands_penetration():
    """Verify 900 MHz penetrates better than 2.4 GHz."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())

    materials = [
        'gypsum_single',
        'gypsum_double',
        'concrete_block',
        'reinforced_concrete',
        'brick',
        'glass_standard',
        'glass_low_e',
        'wood_door',
        'metal_fire_door',
        'elevator_shaft',
    ]

    for mat in materials:
        atten_900 = db.get_deterministic_attenuation(mat, 900000000.0)
        atten_2400 = db.get_deterministic_attenuation(mat, 2400000000.0)
        assert atten_900 <= atten_2400, \
            f"{mat}: 900MHz attenuation {atten_900} > 2.4GHz attenuation {atten_2400}"


def test_no_negative_attenuation():
    """Verify sampled attenuation is never negative."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    rng = np.random.default_rng(42)

    # Sample many times
    for mat_name, freq in db.entries.keys():
        for _ in range(100):
            atten = db.get_attenuation(mat_name, freq, rng)
            assert atten >= 0.0, f"Negative attenuation for {mat_name} at {freq}"


def test_fuzzy_frequency_matching():
    """Test fuzzy frequency matching for unknown frequencies."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    rng = np.random.default_rng(42)

    # Query with a frequency that doesn't exist (1800 MHz)
    # Should match to closest frequency
    atten = db.get_attenuation('gypsum_double', 1800000000.0, rng)
    assert atten >= 0.0


def test_unknown_material_fallback():
    """Test handling of unknown material."""
    db = MaterialRFDatabase.from_yaml(get_materials_path())
    rng = np.random.default_rng(42)

    # Query unknown material should return 0 attenuation
    atten = db.get_attenuation('unknown_material', 2400000000.0, rng)
    assert atten == 0.0
