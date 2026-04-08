#!/usr/bin/env python3
"""
BuildingSpaceGenerator CLI

Usage examples:
  buildingspacegen generate --type medium_office --sqft 25000 --seed 42 --output output/building.json
  buildingspacegen render --type medium_office --sqft 25000 --seed 42 --output output/floorplan.png
  buildingspacegen batch --type medium_office --sqft 25000 --runs 5 --output output/batch.json
  buildingspacegen visualize --type medium_office --sqft 25000 --seed 42 --port 8000
  buildingspacegen visualize-scene --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" --port 8000
  buildingspacegen simulate-scene --input "output/imported-buildings/Millrock Office.graph - Floor 1.json" --port 8000
  buildingspacegen visualize-imported --graph "Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json" --floor "Floor 0" --port 8000
  buildingspacegen simulate-imported --graph "Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json" --floor "Floor 0" --port 8000
  buildingspacegen view --input output/building.json --port 8000
"""
import argparse
import json
import os
import sys

SIMULATION_RADIO_SETTINGS = {
    2400000000.0: {
        "tx_power_dbm": 8.0,
        "sensor_tx_antenna_gain_dbi": -11.0,
        "controller_rx_antenna_gain_dbi": 0.0,
        "min_rssi_dbm": -75.0,
    },
    900000000.0: {
        "tx_power_dbm": 10.0,
        "sensor_tx_antenna_gain_dbi": -5.0,
        "controller_rx_antenna_gain_dbi": 0.0,
        "min_rssi_dbm": -85.0,
    },
}


def _require_uvicorn():
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for browser commands. Install with: pip install uvicorn")
        sys.exit(1)
    return uvicorn


def _serve_scene(scene: dict, port: int) -> None:
    from buildingspacegen.buildingviz.server.app import app, set_scene

    uvicorn = _require_uvicorn()
    set_scene(scene)
    print(f"Starting visualizer at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


def _coerce_floor_selector(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return text

def cmd_generate(args):
    """Generate a building and save JSON."""
    from buildingspacegen.pipeline import PipelineConfig, run_pipeline
    from buildingspacegen.core.enums import BuildingType

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=args.freq,
    )
    result = run_pipeline(config)
    output = args.output or 'output/building.json'
    result.save_json(output)
    print(f"Generated building: {result.building.building_type.value}")
    print(f"  Rooms: {sum(1 for _ in result.building.all_rooms())}")
    print(f"  Devices: {len(result.placement.devices)}")
    for freq, graph in result.path_loss_graphs.items():
        viable = len(graph.get_viable_links(freq))
        total = len(graph.all_links)
        print(f"  Links @ {freq/1e6:.0f} MHz: {viable}/{total} viable")
    print(f"Saved to: {output}")


def cmd_render(args):
    """Render building to PNG using matplotlib."""
    from buildingspacegen.pipeline import PipelineConfig, run_pipeline
    from buildingspacegen.core.enums import BuildingType
    from buildingspacegen.buildingviz.renderers.matplotlib_2d import render_building_2d

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=args.freq if args.freq else [900e6],
    )
    result = run_pipeline(config)
    output = args.output or 'output/floorplan.png'
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

    freq = config.frequencies_hz[0]
    graph = result.path_loss_graphs.get(freq)
    render_building_2d(
        building=result.building,
        devices=result.placement,
        links=graph,
        frequency_hz=freq,
        save_path=output,
    )
    print(f"Rendered to: {output}")


def cmd_batch(args):
    """Run Monte Carlo batch simulation."""
    from buildingspacegen.pipeline import PipelineConfig, BatchConfig, run_batch
    from buildingspacegen.core.enums import BuildingType

    base_config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        frequencies_hz=args.freq,
    )
    batch_config = BatchConfig(
        base_config=base_config,
        num_runs=args.runs,
        seed_start=args.seed_start,
        output_dir=args.output_dir or 'output/batch',
        save_individual=args.save_individual,
    )
    print(f"Running {args.runs} Monte Carlo simulations...")
    summary = run_batch(batch_config)

    output = args.output or 'output/batch_results.json'
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, 'w') as f:
        json.dump(summary.to_dict(), f, indent=2)

    print(f"\nBatch complete: {summary.num_runs} runs")
    for freq, band in summary.per_frequency.items():
        print(f"  @ {freq/1e6:.0f} MHz:")
        print(f"    Viable links: {band.viable_link_fraction.mean:.1%} ± {band.viable_link_fraction.std:.1%}")
        print(f"    Network connectivity: {band.network_connectivity.mean:.1%} ± {band.network_connectivity.std:.1%}")
        print(f"    Mean path loss: {band.mean_path_loss_db.mean:.1f} dB")
    print(f"Saved to: {output}")


def cmd_visualize(args):
    """Generate a building and start the interactive visualizer."""
    from buildingspacegen.pipeline import PipelineConfig, run_pipeline
    from buildingspacegen.core.enums import BuildingType

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)
    _serve_scene(result.to_json(), args.port)

from buildingspacegen.pipeline import PipelineResult
from buildingspacegen.core.enums import DeviceType
from buildingspacegen.core.links import PathLossGraph

def run_single_simulation(result: PipelineResult) -> PipelineResult:
    """
    Simulate a single run on the pipeline result for both 900 MHz and 2.4 GHz networks,
    using appropriate legacy sensor parameters for each band.
    Star networks are the only ones that are viable. Sensors push blindly and controllers within range will receive.
    Viability definition: 80% reception rate which on average is at band-specific minimum RSSI in our experimentation.
    """
    controllers = {
        device.id
        for device in result.placement.devices
        if device.device_type == DeviceType.MAIN_CONTROLLER or device.device_type == DeviceType.SECONDARY_CONTROLLER
    }
    sensors = {
        device.id
        for device in result.placement.devices
        if device.device_type == DeviceType.SENSOR
    }

    out_graphs = {}

    for freq_hz, settings in SIMULATION_RADIO_SETTINGS.items():
        graph = result.path_loss_graphs.get(freq_hz)
        if graph is None:
            out_graphs[freq_hz] = PathLossGraph()
            continue

        best_link_by_sensor = {}
        for link in graph.all_links:
            device_a_id = link.tx_device_id
            device_b_id = link.rx_device_id
            frequency_hz = link.frequency_hz

            if frequency_hz != freq_hz:
                continue

            is_controller_link = (
                (device_a_id in controllers and device_b_id in sensors)
                or (device_b_id in controllers and device_a_id in sensors)
            )
            if not is_controller_link:
                continue

            sensor_id = device_b_id if device_a_id in controllers else device_a_id

            tx_power_dbm = settings["tx_power_dbm"]
            sensor_tx_gain_dbi = settings["sensor_tx_antenna_gain_dbi"]
            controller_rx_gain_dbi = settings["controller_rx_antenna_gain_dbi"]
            min_rssi_dbm = settings["min_rssi_dbm"]

            RSSI_dBm = tx_power_dbm + sensor_tx_gain_dbi + controller_rx_gain_dbi - link.path_loss_db
            link.rx_power_dbm = RSSI_dBm
            link.link_viable = RSSI_dBm >= min_rssi_dbm
            link.link_margin_db = RSSI_dBm - min_rssi_dbm

            current_best = best_link_by_sensor.get(sensor_id)
            if current_best is None or link.rx_power_dbm > current_best.rx_power_dbm:
                best_link_by_sensor[sensor_id] = link

        new_graph = PathLossGraph()
        for link in best_link_by_sensor.values():
            new_graph.add_link(link)
        out_graphs[freq_hz] = new_graph

    simulated = PipelineResult(
        building=result.building,
        placement=result.placement,
        path_loss_graphs=out_graphs,
        config=result.config,
    )
    simulated.annotate_sensor_connectivity()
    return simulated


def build_simulation_scene(result: PipelineResult) -> dict:
    """Serialize a simulated result with band-specific radio assumptions."""
    scene = result.to_json()
    scene["simulation"] = {
        "mode": "single_run",
        "per_frequency": {
            str(int(freq_hz)): settings
            for freq_hz, settings in SIMULATION_RADIO_SETTINGS.items()
        },
    }
    return scene

        

def cmd_simulate(args):
    """Generate a building and start the interactive visualizer."""
    from buildingspacegen.pipeline import PipelineConfig, run_pipeline
    from buildingspacegen.core.enums import BuildingType

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)
    result = run_single_simulation(result)
    _serve_scene(build_simulation_scene(result), args.port)


def cmd_visualize_imported(args):
    """Import a floor, place devices, and visualize the result."""
    from buildingspacegen.pipeline import ImportedPipelineConfig, run_imported_pipeline

    result = run_imported_pipeline(
        ImportedPipelineConfig(
            graph_path=args.graph,
            floor_selector=_coerce_floor_selector(args.floor),
            seed=args.seed,
            frequencies_hz=[900e6, 2.4e9],
        )
    )
    _serve_scene(result.to_json(), args.port)


def cmd_simulate_imported(args):
    """Import a floor, place devices, run the single-run simulation, and visualize the result."""
    from buildingspacegen.pipeline import ImportedPipelineConfig, run_imported_pipeline

    result = run_imported_pipeline(
        ImportedPipelineConfig(
            graph_path=args.graph,
            floor_selector=_coerce_floor_selector(args.floor),
            seed=args.seed,
            frequencies_hz=[900e6, 2.4e9],
        )
    )
    result = run_single_simulation(result)
    _serve_scene(build_simulation_scene(result), args.port)


def cmd_visualize_scene(args):
    """Load a building-only scene JSON, place devices, and visualize the result."""
    from buildingspacegen.pipeline import ExistingBuildingPipelineConfig, run_existing_building_pipeline

    result = run_existing_building_pipeline(
        ExistingBuildingPipelineConfig(
            input_path=args.input,
            seed=args.seed,
            frequencies_hz=[900e6, 2.4e9],
        )
    )
    _serve_scene(result.to_json(), args.port)


def cmd_simulate_scene(args):
    """Load a building-only scene JSON, place devices, run the single-run simulation, and visualize the result."""
    from buildingspacegen.pipeline import ExistingBuildingPipelineConfig, run_existing_building_pipeline

    result = run_existing_building_pipeline(
        ExistingBuildingPipelineConfig(
            input_path=args.input,
            seed=args.seed,
            frequencies_hz=[900e6, 2.4e9],
        )
    )
    result = run_single_simulation(result)
    _serve_scene(build_simulation_scene(result), args.port)


def cmd_view(args):
    """Load an existing JSON file and start the visualizer."""
    with open(args.input) as f:
        scene = json.load(f)
    _serve_scene(scene, args.port)


def main():
    parser = argparse.ArgumentParser(
        prog='buildingspacegen',
        description='BuildingSpaceGenerator — building import, placement, RF simulation, and visualization',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # generate
    p_gen = subparsers.add_parser('generate', help='Generate a building and save JSON')
    p_gen.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_gen.add_argument('--sqft', type=float, required=True)
    p_gen.add_argument('--seed', type=int, default=42)
    p_gen.add_argument('--freq', type=float, nargs='+', default=[900e6, 2.4e9])
    p_gen.add_argument('--output', type=str, default=None)
    p_gen.set_defaults(func=cmd_generate)

    # render
    p_render = subparsers.add_parser('render', help='Render building floor plan to PNG')
    p_render.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_render.add_argument('--sqft', type=float, required=True)
    p_render.add_argument('--seed', type=int, default=42)
    p_render.add_argument('--freq', type=float, nargs='+', default=[900e6])
    p_render.add_argument('--output', type=str, default=None)
    p_render.set_defaults(func=cmd_render)

    # batch
    p_batch = subparsers.add_parser('batch', help='Run Monte Carlo batch simulation')
    p_batch.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_batch.add_argument('--sqft', type=float, required=True)
    p_batch.add_argument('--runs', type=int, default=100)
    p_batch.add_argument('--seed-start', type=int, default=0)
    p_batch.add_argument('--freq', type=float, nargs='+', default=[900e6, 2.4e9])
    p_batch.add_argument('--output', type=str, default=None)
    p_batch.add_argument('--output-dir', type=str, default=None)
    p_batch.add_argument('--save-individual', action='store_true')
    p_batch.set_defaults(func=cmd_batch)

    # visualize
    p_viz = subparsers.add_parser('visualize', help='Generate and visualize in browser')
    p_viz.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_viz.add_argument('--sqft', type=float, required=True)
    p_viz.add_argument('--seed', type=int, default=42)
    p_viz.add_argument('--port', type=int, default=8000)
    p_viz.set_defaults(func=cmd_visualize)

    p_viz_imported = subparsers.add_parser('visualize-imported', help='Import a floor and visualize with placed devices')
    p_viz_imported.add_argument('--graph', required=True)
    p_viz_imported.add_argument('--floor', required=False, default=None)
    p_viz_imported.add_argument('--seed', type=int, default=42)
    p_viz_imported.add_argument('--port', type=int, default=8000)
    p_viz_imported.set_defaults(func=cmd_visualize_imported)

    p_viz_scene = subparsers.add_parser('visualize-scene', help='Load a building-only scene, place devices, and visualize')
    p_viz_scene.add_argument('--input', required=True)
    p_viz_scene.add_argument('--seed', type=int, default=42)
    p_viz_scene.add_argument('--port', type=int, default=8000)
    p_viz_scene.set_defaults(func=cmd_visualize_scene)

    # simulate
    p_sim = subparsers.add_parser('simulate', help='Run Single Monte simulation')
    p_sim.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_sim.add_argument('--sqft', type=float, required=True)
    p_sim.add_argument('--seed', type=int, default=42)
    p_sim.add_argument('--port', type=int, default=8001)
    p_sim.set_defaults(func=cmd_simulate)

    p_sim_imported = subparsers.add_parser('simulate-imported', help='Import a floor and run the single-run simulation')
    p_sim_imported.add_argument('--graph', required=True)
    p_sim_imported.add_argument('--floor', required=False, default=None)
    p_sim_imported.add_argument('--seed', type=int, default=42)
    p_sim_imported.add_argument('--port', type=int, default=8001)
    p_sim_imported.set_defaults(func=cmd_simulate_imported)

    p_sim_scene = subparsers.add_parser('simulate-scene', help='Load a building-only scene and run the single-run simulation')
    p_sim_scene.add_argument('--input', required=True)
    p_sim_scene.add_argument('--seed', type=int, default=42)
    p_sim_scene.add_argument('--port', type=int, default=8001)
    p_sim_scene.set_defaults(func=cmd_simulate_scene)

    # view
    p_view = subparsers.add_parser('view', help='View existing JSON in browser')
    p_view.add_argument('--input', required=True)
    p_view.add_argument('--port', type=int, default=8000)
    p_view.set_defaults(func=cmd_view)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
