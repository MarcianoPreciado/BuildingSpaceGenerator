"""Integration tests for imported Quantum floors."""
from buildingspacegen.pipeline import ImportedPipelineConfig, run_imported_pipeline


def test_run_imported_pipeline_kajima_floor_zero() -> None:
    result = run_imported_pipeline(
        ImportedPipelineConfig(
            graph_path="Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json",
            floor_selector="Floor 0",
            seed=9,
            frequencies_hz=[900e6],
        )
    )

    assert result.building.metadata["source_floor_name"] == "Floor 0"
    assert len(result.building.floors[0].rooms) == 42
    assert len(result.placement.devices) > 0
    assert 900e6 in result.path_loss_graphs
    assert len(result.path_loss_graphs[900e6].all_links) > 0
