"""Reusable glyph helpers for the 2D visualizer."""
from __future__ import annotations

import math
from typing import Mapping, Sequence

from matplotlib.patches import Arc, Circle, RegularPolygon

from buildingspacegen.core.device import Device
from buildingspacegen.core.enums import DeviceType


DEVICE_STYLES = {
    DeviceType.MAIN_CONTROLLER: {
        "shape": "diamond",
        "size": 0.55,
        "facecolor": "#e94560",
        "edgecolor": "white",
        "linewidth": 1.0,
        "alpha": 1.0,
    },
    DeviceType.SECONDARY_CONTROLLER: {
        "shape": "square",
        "size": 0.48,
        "facecolor": "#4FC3F7",
        "edgecolor": "white",
        "linewidth": 1.0,
        "alpha": 1.0,
    },
    DeviceType.SENSOR: {
        "shape": "circle",
        "size": 0.28,
        "facecolor": "#81C784",
        "edgecolor": "white",
        "linewidth": 0.9,
        "alpha": 1.0,
    },
}


def _device_metadata_value(device: Device, name: str, default=None):
    value = getattr(device, name, None)
    if value is not None:
        return value
    metadata = getattr(device, "metadata", None)
    if isinstance(metadata, dict):
        return metadata.get(name, default)
    return default


def _normalize_side(side: object) -> str | None:
    if side is None:
        return None
    side_str = str(side).strip().lower()
    if side_str in {"left", "right"}:
        return side_str
    return None


def wall_unit_vectors(wall) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return wall tangent and left-normal unit vectors."""
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        return (1.0, 0.0), (0.0, 1.0)

    tangent = (dx / length, dy / length)
    left_normal = (-tangent[1], tangent[0])
    return tangent, left_normal


def _wall_point(wall, t: float) -> tuple[float, float]:
    clamped_t = max(0.0, min(1.0, float(t)))
    x = wall.start.x + (wall.end.x - wall.start.x) * clamped_t
    y = wall.start.y + (wall.end.y - wall.start.y) * clamped_t
    return x, y


def _point_to_segment_distance(x: float, y: float, wall) -> float:
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return math.hypot(x - wall.start.x, y - wall.start.y)

    t = ((x - wall.start.x) * dx + (y - wall.start.y) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    px = wall.start.x + t * dx
    py = wall.start.y + t * dy
    return math.hypot(x - px, y - py)


def _infer_mounted_side(device: Device, wall) -> str | None:
    mounted_side = _normalize_side(_device_metadata_value(device, "mounted_side"))
    if mounted_side is not None:
        return mounted_side

    if getattr(device, "room_id", None):
        if device.room_id == wall.room_ids[0]:
            return "left"
        if wall.room_ids[1] is not None and device.room_id == wall.room_ids[1]:
            return "right"

    return None


def _resolve_device_anchor(device: Device, wall_lookup: Mapping[str, object] | None) -> tuple[float, float]:
    """Resolve a render-space point for a device."""
    if not getattr(device, "wall_id", "") or not wall_lookup:
        return device.position.x, device.position.y

    wall = wall_lookup.get(device.wall_id)
    if wall is None:
        return device.position.x, device.position.y

    offset = _device_metadata_value(device, "offset_from_wall_m")
    if offset is None:
        offset = _device_metadata_value(device, "wall_mount_offset_m", 0.0)
    offset = float(offset or 0.0)
    if offset <= 0.0:
        return device.position.x, device.position.y

    mounted_side = _infer_mounted_side(device, wall)
    if mounted_side is None:
        return device.position.x, device.position.y

    position_along_wall = _device_metadata_value(device, "position_along_wall")
    if position_along_wall is None:
        tangent, _ = wall_unit_vectors(wall)
        dx = device.position.x - wall.start.x
        dy = device.position.y - wall.start.y
        seg_dx = wall.end.x - wall.start.x
        seg_dy = wall.end.y - wall.start.y
        seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy
        if seg_len_sq <= 1e-12:
            position_along_wall = 0.0
        else:
            position_along_wall = (dx * tangent[0] + dy * tangent[1]) / math.sqrt(seg_len_sq)

    wall_x, wall_y = _wall_point(wall, position_along_wall if position_along_wall is not None else 0.5)
    dist_to_wall = _point_to_segment_distance(device.position.x, device.position.y, wall)
    if dist_to_wall > max(0.03, offset * 0.35):
        return device.position.x, device.position.y

    tangent, left_normal = wall_unit_vectors(wall)
    normal = left_normal if mounted_side == "left" else (-left_normal[0], -left_normal[1])
    candidate = (wall_x + normal[0] * offset, wall_y + normal[1] * offset)
    return candidate


def default_device_style(device_type: DeviceType) -> dict:
    """Return the default visual style for a device type."""
    return dict(DEVICE_STYLES[device_type])


def make_door_swing_patch(door, wall, radius: float = 0.9, color: str = "#A1887F", zorder: int = 4) -> Arc:
    """Build a quarter-arc swing symbol for a door."""
    center_x, center_y = _wall_point(wall, door.position_along_wall)
    tangent, _ = wall_unit_vectors(wall)
    wall_angle_deg = math.degrees(math.atan2(tangent[1], tangent[0]))
    return Arc(
        (center_x, center_y),
        2.0 * radius,
        2.0 * radius,
        angle=0.0,
        theta1=wall_angle_deg,
        theta2=wall_angle_deg + 90.0,
        color=color,
        linewidth=1.15,
        alpha=0.55,
        zorder=zorder,
    )


def make_door_leaf_line(door, wall, radius: float = 0.9, color: str = "#A1887F", zorder: int = 4):
    """Build a thin line indicating the door leaf opening."""
    center_x, center_y = _wall_point(wall, door.position_along_wall)
    tangent, _ = wall_unit_vectors(wall)
    wall_angle_deg = math.degrees(math.atan2(tangent[1], tangent[0]))
    open_angle = math.radians(wall_angle_deg + 90.0)
    open_x = center_x + radius * math.cos(open_angle)
    open_y = center_y + radius * math.sin(open_angle)
    return (center_x, center_y), (open_x, open_y), color, zorder


def draw_door(ax, wall, door, color: str = "#A1887F", markersize: int = 6, zorder: int = 4) -> None:
    """Draw a quarter-arc door swing symbol."""
    if wall is None:
        return

    radius = max(float(getattr(door, "width", 0.9)), 0.2)
    swing = make_door_swing_patch(door, wall, radius=radius, color=color, zorder=zorder)
    ax.add_patch(swing)
    (x0, y0), (x1, y1), line_color, line_zorder = make_door_leaf_line(
        door,
        wall,
        radius=radius,
        color=color,
        zorder=zorder + 0.1,
    )
    ax.plot([x0, x1], [y0, y1], color=line_color, linewidth=1.0, alpha=0.6, zorder=line_zorder)


def make_wall_tangent_device_patch(
    device: Device,
    wall,
    center: tuple[float, float],
    style: dict,
):
    """Build a device glyph aligned to a wall when possible."""
    tangent, _ = wall_unit_vectors(wall)
    wall_angle = math.atan2(tangent[1], tangent[0])
    shape = style.get("shape", "circle")
    size = float(style.get("size", 0.35))
    facecolor = style.get("facecolor", "#999999")
    edgecolor = style.get("edgecolor", "white")
    linewidth = float(style.get("linewidth", 1.0))
    alpha = float(style.get("alpha", 1.0))

    if shape == "diamond":
        return RegularPolygon(
            center,
            numVertices=4,
            radius=size,
            orientation=wall_angle + math.pi / 4.0,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            alpha=alpha,
            zorder=5,
        )
    if shape == "square":
        return RegularPolygon(
            center,
            numVertices=4,
            radius=size,
            orientation=wall_angle,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            alpha=alpha,
            zorder=5,
        )

    return Circle(
        center,
        radius=size,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        alpha=alpha,
        zorder=5,
    )


def draw_devices(
    ax,
    devices: Sequence[Device],
    device_markers: Mapping[DeviceType, tuple[str, int, str]],
    show_device_labels: bool = False,
    wall_lookup: Mapping[str, object] | None = None,
) -> None:
    """Draw devices as patches with wall-aware placement when possible."""
    for device in devices:
        style = default_device_style(device.device_type)
        style["facecolor"] = device_markers.get(device.device_type, ("o", 0, style["facecolor"]))[2]
        center = _resolve_device_anchor(device, wall_lookup)
        wall = wall_lookup.get(device.wall_id) if wall_lookup and getattr(device, "wall_id", "") else None

        if wall is not None:
            patch = make_wall_tangent_device_patch(device, wall, center, style)
        else:
            patch = make_wall_tangent_device_patch(
                device,
                type("_WallLike", (), {"start": device.position, "end": device.position})(),
                center,
                style,
            )
        ax.add_patch(patch)

        if show_device_labels:
            ax.annotate(
                device.id,
                center,
                fontsize=5,
                ha="center",
            )
