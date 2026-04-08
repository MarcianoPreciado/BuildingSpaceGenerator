from __future__ import annotations

"""RF geometry computations for path loss."""
from collections import defaultdict

from buildingspacegen.core.geometry import Point2D, LineSegment2D
from buildingspacegen.core.model import Building


def find_intersected_walls(
    tx_pos: Point2D,
    rx_pos: Point2D,
    building: Building,
    tx_wall_id: str | None = None,
    tx_mounted_side: str | None = None,
    tx_offset_from_wall_m: float = 0.0,
    rx_wall_id: str | None = None,
    rx_mounted_side: str | None = None,
    rx_offset_from_wall_m: float = 0.0,
) -> list[dict]:
    """
    Find all wall segments intersected by the direct path from tx to rx.

    Returns list of dicts with keys:
        'wall_id': str
        'material': str (material name to look up in RF database)
        'is_door': bool (True if intersection is through a door)
    """
    tx_origin = _shift_mount_point(tx_pos, building, tx_wall_id, tx_mounted_side, tx_offset_from_wall_m)
    rx_origin = _shift_mount_point(rx_pos, building, rx_wall_id, rx_mounted_side, rx_offset_from_wall_m)
    ray = LineSegment2D(tx_origin, rx_origin)
    hits = []

    # Build door lookup by wall_id for fast access
    door_by_wall = defaultdict(list)
    for floor in building.floors:
        for door in floor.doors:
            door_by_wall[door.wall_id].append(door)

    for wall in building.all_walls():
        wall_seg = LineSegment2D(wall.start, wall.end)
        # Use intersection_point directly rather than calling intersects() first.
        # The CCW-based intersects() uses a strict inequality that silently misses
        # rays that pass exactly through a wall endpoint (e.g. at a T-junction or
        # room corner).  intersection_point() uses the parametric form with
        # inclusive bounds (0 <= t, u <= 1) and handles these cases correctly.
        intersection = ray.intersection_point(wall_seg)
        if intersection is None:
            continue

        material_name = wall.materials[0].name if wall.materials else "gypsum_double"
        wall_metadata = getattr(wall, "metadata", {}) or {}
        opening_kind = wall_metadata.get("opening_kind")
        is_door = opening_kind in {"door", "garage_door"}

        # Legacy generated buildings represent doors separately; imported floors may split
        # openings into dedicated wall segments and mark them in wall metadata.
        if opening_kind is None:
            for door in door_by_wall.get(wall.id, []):
                wall_length = wall_seg.length()
                if wall_length <= 0:
                    continue
                half_width_frac = (door.width / 2.0) / wall_length
                door_start = door.position_along_wall - half_width_frac
                door_end = door.position_along_wall + half_width_frac

                wall_start = wall.start
                dx = wall.end.x - wall_start.x
                dy = wall.end.y - wall_start.y
                if abs(dx) > abs(dy):
                    t_on_wall = (intersection.x - wall_start.x) / dx if dx != 0 else 0
                else:
                    t_on_wall = (intersection.y - wall_start.y) / dy if dy != 0 else 0

                if door_start <= t_on_wall <= door_end:
                    material_name = door.material.name
                    opening_kind = "door"
                    is_door = True
                    break

        hits.append({
            "wall_id": wall.id,
            "material": material_name,
            "is_door": is_door,
            "opening_kind": opening_kind,
            "_intersection_xy": (round(intersection.x, 6), round(intersection.y, 6)),
        })

    deduped: dict[tuple[float, float], dict] = {}
    for hit in hits:
        key = hit["_intersection_xy"]
        current = deduped.get(key)
        if current is None or _prefer_intersection_hit(hit, current):
            deduped[key] = hit

    results = []
    for hit in deduped.values():
        hit.pop("_intersection_xy", None)
        results.append(hit)

    return results


def _prefer_intersection_hit(candidate: dict, current: dict) -> bool:
    """Prefer explicit openings over coincident solid-wall duplicates."""
    candidate_priority = 1 if candidate.get("opening_kind") else 0
    current_priority = 1 if current.get("opening_kind") else 0
    if candidate_priority != current_priority:
        return candidate_priority > current_priority
    return False


def _shift_mount_point(
    point: Point2D,
    building: Building,
    wall_id: str | None,
    mounted_side: str | None,
    offset_from_wall_m: float,
) -> Point2D:
    """Shift a wall-centered point into the mounted room before tracing the ray."""
    if not wall_id or not mounted_side or offset_from_wall_m <= 0.0:
        return point

    wall = building.get_wall(wall_id)
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = wall.start.distance_to(wall.end)
    if length <= 1e-10:
        return point

    normal_x = -dy / length
    normal_y = dx / length
    sign = 1.0 if mounted_side == "left" else -1.0
    return Point2D(
        point.x + sign * normal_x * offset_from_wall_m,
        point.y + sign * normal_y * offset_from_wall_m,
    )
