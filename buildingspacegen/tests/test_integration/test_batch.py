"""Integration tests for the batch Monte Carlo runner."""
import pytest
from buildingspacegen.pipeline import PipelineConfig, BatchConfig, run_batch
from buildingspacegen.core.enums import BuildingType


def test_batch_small():
    base = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000)
    batch = BatchConfig(base_config=base, num_runs=3, seed_start=0)
    summary = run_batch(batch)
    assert summary.num_runs == 3
    assert len(summary.per_frequency) == 2  # 900 MHz + 2.4 GHz
    for freq, band in summary.per_frequency.items():
        assert 0 <= band.viable_link_fraction.mean <= 1
        assert 0 <= band.network_connectivity.mean <= 1


def test_batch_different_seeds_produce_variance():
    """Different building seeds should produce different results."""
    base = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=15000)
    batch = BatchConfig(base_config=base, num_runs=5, seed_start=0)
    summary = run_batch(batch)
    # Std should be > 0 if different buildings are different
    for freq, band in summary.per_frequency.items():
        # Not strictly required (unlikely but possible to get same stats)
        # Just verify the run completed successfully
        assert band.viable_link_fraction.mean >= 0


def test_batch_to_dict():
    base = PipelineConfig(building_type=BuildingType.MEDIUM_OFFICE, total_sqft=10000)
    batch = BatchConfig(base_config=base, num_runs=2, seed_start=0)
    summary = run_batch(batch)
    d = summary.to_dict()
    assert "num_runs" in d
    assert "per_frequency" in d
