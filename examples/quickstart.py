#!/usr/bin/env python3
"""
Quick demonstration of the BuildingSpaceGenerator.
Run: python examples/quickstart.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from buildingspacegen.pipeline import run_pipeline, PipelineConfig
from buildingspacegen.core.enums import BuildingType, DeviceType

print("=" * 60)
print("BuildingSpaceGenerator Quickstart Demo")
print("=" * 60)

# Generate a medium office building
config = PipelineConfig(
    building_type=BuildingType.MEDIUM_OFFICE,
    total_sqft=25000,
    seed=42,
    frequencies_hz=[900e6, 2.4e9],
)

print(f"\nGenerating {config.building_type.value} building ({config.total_sqft:,.0f} sqft, seed={config.seed})...")
result = run_pipeline(config)

# Print building summary
building = result.building
rooms = list(building.all_rooms())
print(f"\nBuilding Generated:")
print(f"   Type: {building.building_type.value}")
print(f"   Total area: {building.total_area_sqft:,.0f} sqft")
print(f"   Floors: {len(building.floors)}")
print(f"   Rooms: {len(rooms)}")

# Room breakdown
room_counts = {}
for r in rooms:
    room_counts[r.room_type.value] = room_counts.get(r.room_type.value, 0) + 1
print("\n   Room breakdown:")
for rtype, count in sorted(room_counts.items()):
    print(f"     {rtype}: {count}")

# Device summary
devices = result.placement.devices
print(f"\nDevices Placed: {len(devices)} total")
for dtype in DeviceType:
    count = len([d for d in devices if d.device_type == dtype])
    print(f"   {dtype.value}: {count}")

# Path loss summary
print("\nRF Link Analysis:")
for freq, graph in result.path_loss_graphs.items():
    all_links = graph.all_links
    viable = graph.get_viable_links(freq)
    if all_links:
        import statistics
        mean_loss = statistics.mean(l.path_loss_db for l in all_links)
        mean_rx = statistics.mean(l.rx_power_dbm for l in all_links)
        print(f"   @ {freq/1e6:.0f} MHz:")
        print(f"     Total links: {len(all_links)}")
        print(f"     Viable: {len(viable)} ({len(viable)/len(all_links):.1%})")
        print(f"     Mean path loss: {mean_loss:.1f} dB")
        print(f"     Mean RX power: {mean_rx:.1f} dBm")

# Save output
os.makedirs("output", exist_ok=True)
out_path = "output/demo_building.json"
result.save_json(out_path)
print(f"\nSaved to {out_path}")
print("\nTo visualize: buildingspacegen visualize --type medium_office --sqft 25000 --seed 42")
print("=" * 60)
