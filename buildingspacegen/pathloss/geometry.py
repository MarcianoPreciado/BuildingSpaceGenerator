"""RF geometry computations for path loss."""
from buildingspacegen.core.geometry import Point2D, LineSegment2D
from buildingspacegen.core.model import Building


def find_intersected_walls(
    tx_pos: Point2D,
    rx_pos: Point2D,
    building: Building,
) -> list[dict]:
    """
    Find all wall segments intersected by the direct path from tx to rx.

    Returns list of dicts with keys:
        'wall_id': str
        'material': str (material name to look up in RF database)
        'is_door': bool (True if intersection is through a door)
    """
    ray = LineSegment2D(tx_pos, rx_pos)
    results = []

    # Build door lookup by wall_id for fast access
    door_by_wall = {}
    for floor in building.floors:
        for door in floor.doors:
            door_by_wall[door.wall_id] = door

    for wall in building.all_walls():
        wall_seg = LineSegment2D(wall.start, wall.end)
        if not ray.intersects(wall_seg):
            continue

        intersection = ray.intersection_point(wall_seg)
        if intersection is None:
            continue

        # Determine material to use
        material_name = wall.materials[0].name if wall.materials else "gypsum_double"
        is_door = False

        # Check if there's a door on this wall and if the intersection is within door span
        if wall.id in door_by_wall:
            door = door_by_wall[wall.id]
            wall_length = wall_seg.length()
            if wall_length > 0:
                # Door occupies [pos - half_width, pos + half_width] along the wall
                half_width_frac = (door.width / 2.0) / wall_length
                door_start = door.position_along_wall - half_width_frac
                door_end = door.position_along_wall + half_width_frac

                # Find the t parameter of intersection along the wall
                wall_start = wall.start
                dx = wall.end.x - wall_start.x
                dy = wall.end.y - wall_start.y
                if abs(dx) > abs(dy):
                    t_on_wall = (intersection.x - wall_start.x) / dx if dx != 0 else 0
                else:
                    t_on_wall = (intersection.y - wall_start.y) / dy if dy != 0 else 0

                if door_start <= t_on_wall <= door_end:
                    material_name = door.material.name
                    is_door = True

        results.append({
            'wall_id': wall.id,
            'material': material_name,
            'is_door': is_door,
        })

    return results
