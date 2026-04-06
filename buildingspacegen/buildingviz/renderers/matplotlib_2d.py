"""Matplotlib 2D renderer for BuildingSpaceGenerator floor plans."""
from typing import Optional
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.cm import get_cmap
import numpy as np

from buildingspacegen.core.model import Building
from buildingspacegen.core.device import DevicePlacement
from buildingspacegen.core.links import PathLossGraph
from buildingspacegen.core.enums import RoomType, DeviceType, WallMaterial


# Color palette for room types
ROOM_COLORS = {
    RoomType.OPEN_OFFICE: '#4CAF50',
    RoomType.PRIVATE_OFFICE: '#2196F3',
    RoomType.CONFERENCE: '#FFC107',
    RoomType.LOBBY: '#9C27B0',
    RoomType.CORRIDOR: '#607D8B',
    RoomType.RESTROOM: '#009688',
    RoomType.KITCHEN_BREAK: '#FF5722',
    RoomType.MECHANICAL: '#455A64',
    RoomType.IT_SERVER: '#37474F',
    RoomType.STORAGE: '#795548',
    RoomType.WAREHOUSE_BAY: '#8BC34A',
    RoomType.LOADING_DOCK: '#CDDC39',
    RoomType.STAIRWELL: '#78909C',
    RoomType.ELEVATOR: '#546E7A',
}

ROOM_FILL_COLORS = {
    RoomType.OPEN_OFFICE: 'rgba(76,175,80,0.18)',
    RoomType.PRIVATE_OFFICE: 'rgba(33,150,243,0.18)',
    RoomType.CONFERENCE: 'rgba(255,193,7,0.22)',
    RoomType.LOBBY: 'rgba(156,39,176,0.18)',
    RoomType.CORRIDOR: 'rgba(96,125,139,0.15)',
    RoomType.RESTROOM: 'rgba(0,150,136,0.18)',
    RoomType.KITCHEN_BREAK: 'rgba(255,87,34,0.18)',
    RoomType.MECHANICAL: 'rgba(69,90,100,0.25)',
    RoomType.IT_SERVER: 'rgba(55,71,79,0.30)',
    RoomType.STORAGE: 'rgba(121,85,72,0.20)',
    RoomType.WAREHOUSE_BAY: 'rgba(139,195,74,0.18)',
    RoomType.LOADING_DOCK: 'rgba(205,220,57,0.22)',
    RoomType.STAIRWELL: 'rgba(120,144,156,0.25)',
    RoomType.ELEVATOR: 'rgba(84,110,122,0.30)',
}

MATERIAL_COLORS = {
    WallMaterial.GYPSUM_SINGLE: '#B4B4B4',
    WallMaterial.GYPSUM_DOUBLE: '#969696',
    WallMaterial.CONCRETE_BLOCK: '#5A5A5A',
    WallMaterial.REINFORCED_CONCRETE: '#3C3C3C',
    WallMaterial.BRICK: '#8D6E63',
    WallMaterial.GLASS_STANDARD: '#81D4FA',
    WallMaterial.GLASS_LOW_E: '#4FC3F7',
    WallMaterial.WOOD_DOOR: '#A1887F',
    WallMaterial.METAL_FIRE_DOOR: '#546E7A',
    WallMaterial.ELEVATOR_SHAFT: '#37474F',
}


def render_building_2d(
    building: Building,
    devices: Optional[DevicePlacement] = None,
    links: Optional[PathLossGraph] = None,
    frequency_hz: Optional[float] = None,
    figsize: tuple = (16, 12),
    show_room_labels: bool = True,
    show_device_labels: bool = False,
    link_color_range: tuple = (-100, -40),
    save_path: Optional[str] = None,
) -> plt.Figure:
    """Render building floor plan with devices and links."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_aspect('equal')
    ax.set_facecolor('#F5F5F5')

    for floor in building.floors:
        # Draw room polygons with fills
        for room in floor.rooms:
            verts = [(v.x, v.y) for v in room.polygon.vertices]
            color = ROOM_COLORS.get(room.room_type, '#999999')
            polygon = MplPolygon(
                verts, closed=True,
                facecolor=color, alpha=0.15,
                edgecolor=color, linewidth=1.5
            )
            ax.add_patch(polygon)

            # Draw room labels
            if show_room_labels:
                centroid = room.polygon.centroid()
                label = f"{room.room_type.value.replace('_', ' ').title()}\n{room.area_sqft:.0f} sqft"
                ax.text(
                    centroid.x, centroid.y, label,
                    ha='center', va='center',
                    fontsize=7, color='#333333',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7, edgecolor='none')
                )

        # Draw walls
        for wall in floor.walls:
            mat = wall.materials[0] if wall.materials else None
            mat_name = mat.name if mat else 'gypsum_double'

            try:
                mat_enum = WallMaterial(mat_name)
                color = MATERIAL_COLORS.get(mat_enum, '#757575')
            except ValueError:
                color = '#757575'

            lw = 3.0 if wall.is_exterior else 1.5
            if mat_name and ('concrete' in mat_name or 'brick' in mat_name):
                lw += 1.0

            ax.plot(
                [wall.start.x, wall.end.x],
                [wall.start.y, wall.end.y],
                color=color, linewidth=lw,
                solid_capstyle='round', zorder=3
            )

        # Draw doors as small circles
        for door in floor.doors:
            wall = next((w for w in floor.walls if w.id == door.wall_id), None)
            if wall:
                dx = wall.end.x - wall.start.x
                dy = wall.end.y - wall.start.y
                door_x = wall.start.x + dx * door.position_along_wall
                door_y = wall.start.y + dy * door.position_along_wall
                ax.plot(
                    door_x, door_y, 'o',
                    color='#A1887F', markersize=6, zorder=4
                )

    # Draw links as lines with color gradient
    if links and frequency_hz:
        cmap = get_cmap('RdYlGn')
        min_dbm, max_dbm = link_color_range

        if devices:
            device_map = {d.id: d for d in devices.devices}
            viable_links = links.get_viable_links(frequency_hz)

            for link in viable_links:
                tx = device_map.get(link.tx_device_id)
                rx = device_map.get(link.rx_device_id)
                if tx and rx:
                    # Normalize RX power to [0, 1] for color map
                    t = (link.rx_power_dbm - min_dbm) / (max_dbm - min_dbm)
                    t = max(0, min(1, t))
                    color = cmap(t)
                    ax.plot(
                        [tx.position.x, rx.position.x],
                        [tx.position.y, rx.position.y],
                        color=color, alpha=0.4, linewidth=0.8, zorder=1
                    )

    # Draw devices
    if devices:
        device_markers = {
            DeviceType.MAIN_CONTROLLER: ('D', 10, '#e94560'),
            DeviceType.SECONDARY_CONTROLLER: ('s', 8, '#4FC3F7'),
            DeviceType.SENSOR: ('o', 6, '#81C784'),
        }

        for dtype, (marker, size, color) in device_markers.items():
            devs = devices.get_devices_by_type(dtype)
            if devs:
                xs = [d.position.x for d in devs]
                ys = [d.position.y for d in devs]
                ax.scatter(
                    xs, ys, marker=marker, s=size**2,
                    c=color, zorder=5, label=dtype.value.replace('_', ' ').title(),
                    edgecolors='white', linewidths=1
                )

                if show_device_labels:
                    for d in devs:
                        ax.annotate(
                            d.id, (d.position.x, d.position.y),
                            fontsize=5, ha='center'
                        )

    # Build legend
    legend_elements = []
    for rt in RoomType:
        if rt in ROOM_COLORS:
            from matplotlib.patches import Patch
            legend_elements.append(
                Patch(
                    facecolor=ROOM_COLORS[rt], alpha=0.5,
                    label=rt.value.replace('_', ' ').title()
                )
            )

    if devices:
        from matplotlib.lines import Line2D
        for dtype, (marker, size, color) in device_markers.items():
            if any(d.device_type == dtype for d in devices.devices):
                legend_elements.append(
                    Line2D(
                        [0], [0], marker=marker, color='w',
                        markerfacecolor=color, markersize=size/2,
                        label=dtype.value.replace('_', ' ').title(),
                        markeredgecolor='white', markeredgewidth=0.5
                    )
                )

    ax.legend(
        handles=legend_elements, loc='upper right',
        fontsize=8, ncol=2, framealpha=0.95
    )

    ax.set_title(
        f"Building: {building.building_type.value} | {building.total_area_sqft:.0f} sqft | Seed: {building.seed}",
        fontsize=12, fontweight='bold'
    )
    ax.set_xlabel('X (meters)', fontsize=10)
    ax.set_ylabel('Y (meters)', fontsize=10)
    ax.grid(True, alpha=0.2, linestyle='--')
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')

    return fig
