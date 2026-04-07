#!/usr/bin/env python3
"""
BuildingSpaceGenerator CLI

Usage examples:
  buildingspacegen generate --type medium_office --sqft 25000 --seed 42 --output output/building.json
  buildingspacegen render --type medium_office --sqft 25000 --seed 42 --output output/floorplan.png
  buildingspacegen batch --type medium_office --sqft 25000 --runs 5 --output output/batch.json
  buildingspacegen visualize --type medium_office --sqft 25000 --seed 42 --port 8000
  buildingspacegen view --input output/building.json --port 8000
"""
import argparse
import json
import os
import sys

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
    from buildingspacegen.buildingviz.server.app import set_scene

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for visualize command. Install with: pip install uvicorn")
        sys.exit(1)

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)
    scene = result.to_json()

    # Inject scene into the server
    set_scene(scene)

    from buildingspacegen.buildingviz.server.app import app
    print(f"Starting visualizer at http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)

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
    controllers = [
        device.id
        for device in result.placement.devices
        if device.device_type == DeviceType.MAIN_CONTROLLER or device.device_type == DeviceType.SECONDARY_CONTROLLER
    ]

    # Radio parameters for each frequency (extend as needed)
    radio_settings = {
        2400000000.0: {
            "tx_power_dBm": 4,                # 2.4 GHz legacy
            "sensor_ant_gain_dBi": -11,
            "controller_ant_gain_dBi": 10,
            "min_RSSI_dBm": -60, # Where we hit the knee of the curve
        },
        900000000.0: {
            "tx_power_dBm": 4,
            "sensor_ant_gain_dBi": -5,
            "controller_ant_gain_dBi": 0,
            "min_RSSI_dBm": -85,             # Where we hit the knee of the curve
        },
    }

    out_graphs = {}

    for freq_hz, settings in radio_settings.items():
        graph = result.path_loss_graphs.get(freq_hz)
        if graph is None:
            out_graphs[freq_hz] = PathLossGraph()
            continue

        processed_links = []
        for link in graph.all_links:
            device_a_id = link.tx_device_id
            device_b_id = link.rx_device_id
            frequency_hz = link.frequency_hz

            if (device_a_id in controllers or device_b_id in controllers) and frequency_hz == freq_hz:
                controller_id = device_a_id if device_a_id in controllers else device_b_id
                sensor_id = device_b_id if device_a_id in controllers else device_a_id
                # Uncomment for debug:
                # print(link)

                # Paint the link with frequency-specific radio parameters
                tx_power_dBm = settings["tx_power_dBm"]
                sensor_ant_gain_dBi = settings["sensor_ant_gain_dBi"]
                controller_ant_gain_dBi = settings["controller_ant_gain_dBi"]
                min_RSSI_dBm = settings["min_RSSI_dBm"]

                RSSI_dBm = tx_power_dBm + sensor_ant_gain_dBi + controller_ant_gain_dBi - link.path_loss_db
                if RSSI_dBm >= min_RSSI_dBm:
                    # Uncomment for debug:
                    # print(f"Link {link.tx_device_id} -> {link.rx_device_id} is viable ({freq_hz/1e6:.0f} MHz)")
                    link.link_viable = True
                    link.link_margin_db = RSSI_dBm - min_RSSI_dBm
                link.rx_power_dbm = RSSI_dBm
                processed_links.append(link)
        new_graph = PathLossGraph()
        for link in processed_links:
            new_graph.add_link(link)
        out_graphs[freq_hz] = new_graph

    return PipelineResult(
        building=result.building,
        placement=result.placement,
        path_loss_graphs=out_graphs,
        config=result.config,
    )

        

def cmd_simulate(args):
    """Generate a building and start the interactive visualizer."""
    from buildingspacegen.pipeline import PipelineConfig, run_pipeline
    from buildingspacegen.core.enums import BuildingType
    from buildingspacegen.buildingviz.server.app import set_scene

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for visualize command. Install with: pip install uvicorn")
        sys.exit(1)

    config = PipelineConfig(
        building_type=BuildingType(args.type),
        total_sqft=args.sqft,
        seed=args.seed,
        frequencies_hz=[900e6, 2.4e9],
    )
    result = run_pipeline(config)
    # result is a PipelineResult
    result = run_single_simulation(result)
    # need to change result's PipelineResult.path_loss_graphs.graph to represent chosen output
    scene = result.to_json()

    # Inject scene into the server
    set_scene(scene)

    from buildingspacegen.buildingviz.server.app import app
    print(f"Starting visualizer at http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def cmd_view(args):
    """Load an existing JSON file and start the visualizer."""
    from buildingspacegen.buildingviz.server.app import set_scene

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required for view command. Install with: pip install uvicorn")
        sys.exit(1)

    with open(args.input) as f:
        scene = json.load(f)
    set_scene(scene)

    from buildingspacegen.buildingviz.server.app import app
    print(f"Starting visualizer at http://localhost:{args.port}")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


def main():
    parser = argparse.ArgumentParser(
        prog='buildingspacegen',
        description='BuildingSpaceGenerator — procedural floor plan generator for WSN simulation',
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

    # simulate
    p_sim = subparsers.add_parser('simulate', help='Run Single Monte simulation')
    p_sim.add_argument('--type', required=True, choices=['medium_office', 'large_office', 'warehouse'])
    p_sim.add_argument('--sqft', type=float, required=True)
    p_sim.add_argument('--seed', type=int, default=42)
    p_sim.add_argument('--port', type=int, default=8001)
    p_sim.set_defaults(func=cmd_simulate)

    # view
    p_view = subparsers.add_parser('view', help='View existing JSON in browser')
    p_view.add_argument('--input', required=True)
    p_view.add_argument('--port', type=int, default=8000)
    p_view.set_defaults(func=cmd_view)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
