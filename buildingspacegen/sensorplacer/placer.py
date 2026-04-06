"""Device placement engine."""
import math
import numpy as np
from buildingspacegen.core.model import Building, WallSegment
from buildingspacegen.core.geometry import Point2D, Point3D
from buildingspacegen.core.device import Device, DevicePlacement, RadioProfile, PlacementRules
from buildingspacegen.core.enums import DeviceType, RoomType


def place_devices(
    building: Building,
    rules: PlacementRules,
    radio_profiles: dict[DeviceType, RadioProfile],
    seed: int,
) -> DevicePlacement:
    """
    Place devices (main controllers, secondary controllers, sensors) in a building.

    Args:
        building: Building model
        rules: Placement rules
        radio_profiles: Radio profiles by device type
        seed: Random seed (uses seed + 1 per reproducibility contract)

    Returns:
        DevicePlacement with all placed devices
    """
    rng = np.random.default_rng(seed + 1)  # +1 per reproducibility contract
    devices = []
    device_counter = [0]

    def new_id():
        device_counter[0] += 1
        return f"dev_{device_counter[0]:04d}"

    # 1. Main Controllers
    total_sqft = building.total_area_sqft
    mc_count = max(1, math.ceil(total_sqft * rules.main_controller_per_sqft))
    mc_profile = radio_profiles.get(DeviceType.MAIN_CONTROLLER)

    if mc_count == 1 and rules.main_controller_prefer_center:
        # Find wall position closest to building centroid
        centroid = building.footprint.centroid()
        best_wall, best_t, best_room = _find_wall_closest_to_point(building, centroid)
        pos = _wall_point(best_wall, best_t, rules.main_controller_wall_height_m)
        devices.append(Device(
            id=new_id(),
            device_type=DeviceType.MAIN_CONTROLLER,
            position=pos,
            room_id=best_room.id,
            wall_id=best_wall.id,
            radio_profile=mc_profile,
        ))
    else:
        # k-means on room centroids, snap to nearest wall
        all_rooms = [r for r in building.all_rooms() if r.room_type != RoomType.CORRIDOR]
        if not all_rooms:
            all_rooms = list(building.all_rooms())
        centroids = [r.polygon.centroid() for r in all_rooms]
        centers = _kmeans(centroids, mc_count, rng)
        for center in centers:
            best_wall, best_t, best_room = _find_wall_closest_to_point(building, center)
            pos = _wall_point(best_wall, best_t, rules.main_controller_wall_height_m)
            devices.append(Device(
                id=new_id(),
                device_type=DeviceType.MAIN_CONTROLLER,
                position=pos,
                room_id=best_room.id,
                wall_id=best_wall.id,
                radio_profile=mc_profile,
            ))

    # 2. Secondary Controllers
    sc_count = max(1, math.ceil(total_sqft * rules.secondary_controller_per_sqft))
    sc_profile = radio_profiles.get(DeviceType.SECONDARY_CONTROLLER)
    existing_positions = [d.position for d in devices]

    for _ in range(sc_count):
        # Farthest-point greedy: pick wall position that maximizes min distance to existing devices
        best_wall, best_t, best_room = _find_farthest_wall_position(
            building, existing_positions, rules.secondary_controller_wall_height_m
        )
        pos = _wall_point(best_wall, best_t, rules.secondary_controller_wall_height_m)
        devices.append(Device(
            id=new_id(),
            device_type=DeviceType.SECONDARY_CONTROLLER,
            position=pos,
            room_id=best_room.id,
            wall_id=best_wall.id,
            radio_profile=sc_profile,
        ))
        existing_positions.append(pos)

    # 3. Sensors
    sensor_profile = radio_profiles.get(DeviceType.SENSOR)
    for floor in building.floors:
        for room in floor.rooms:
            if room.room_type in rules.excluded_room_types:
                continue
            count = max(rules.sensor_min_per_room, math.ceil(room.area_sqft * rules.sensor_per_sqft))
            sensor_positions = _distribute_on_walls(
                room, floor, count, rules.sensor_wall_height_m, rules.sensor_min_spacing_m
            )
            for wall_id, t in sensor_positions:
                wall = building.get_wall(wall_id)
                pos = _wall_point(wall, t, rules.sensor_wall_height_m)
                devices.append(Device(
                    id=new_id(),
                    device_type=DeviceType.SENSOR,
                    position=pos,
                    room_id=room.id,
                    wall_id=wall_id,
                    radio_profile=sensor_profile,
                ))

    return DevicePlacement(
        building_seed=building.seed,
        devices=devices,
        placement_rules=rules,
    )


def _find_wall_closest_to_point(building: Building, point: Point2D) -> tuple:
    """
    Find the wall segment and position on it closest to a given 2D point.

    Returns:
        (WallSegment, t, Room) where t is fraction along wall [0, 1]
    """
    min_distance = float('inf')
    best_wall = None
    best_t = 0
    best_room = None

    # Search all interior walls
    for wall in building.all_walls():
        if wall.is_exterior:
            continue

        # Find closest point on wall to the given point
        wall_start = wall.start
        wall_end = wall.end
        dx = wall_end.x - wall_start.x
        dy = wall_end.y - wall_start.y
        wall_len_sq = dx*dx + dy*dy

        if wall_len_sq < 1e-10:
            # Degenerate wall
            continue

        # Parameter t of closest point on wall
        t = max(0, min(1, ((point.x - wall_start.x) * dx + (point.y - wall_start.y) * dy) / wall_len_sq))
        closest_x = wall_start.x + t * dx
        closest_y = wall_start.y + t * dy
        dist = math.sqrt((closest_x - point.x)**2 + (closest_y - point.y)**2)

        if dist < min_distance:
            min_distance = dist
            best_wall = wall
            best_t = t
            # Get the first room for this wall
            room_a = building.get_room(wall.room_ids[0])
            best_room = room_a

    if best_wall is None:
        # Fallback: use first interior wall
        for wall in building.all_walls():
            if not wall.is_exterior:
                best_wall = wall
                best_t = 0.5
                best_room = building.get_room(wall.room_ids[0])
                break

    return best_wall, best_t, best_room


def _find_farthest_wall_position(
    building: Building, existing_positions: list[Point3D], height_m: float
) -> tuple:
    """
    Find a wall position that maximizes minimum distance to existing positions.

    Returns:
        (WallSegment, t, Room)
    """
    max_min_distance = -1
    best_wall = None
    best_t = 0.5
    best_room = None

    # Sample candidate positions: midpoint of each room's walls
    candidates = []
    for room in building.all_rooms():
        if room.room_type in [RoomType.ELEVATOR, RoomType.STAIRWELL]:
            continue
        # Add midpoint of the room
        room_centroid = room.polygon.centroid()
        candidates.append((room_centroid, room))

    for candidate_point, candidate_room in candidates:
        wall, t, room = _find_wall_closest_to_point(building, candidate_point)
        if wall is None:
            continue

        # Compute position and its min distance to existing
        pos = _wall_point(wall, t, height_m)
        min_dist = min(
            (pos.distance_to(ep) for ep in existing_positions),
            default=float('inf')
        )

        if min_dist > max_min_distance:
            max_min_distance = min_dist
            best_wall = wall
            best_t = t
            best_room = room

    # Fallback
    if best_wall is None:
        for wall in building.all_walls():
            if not wall.is_exterior:
                best_wall = wall
                best_t = 0.5
                best_room = building.get_room(wall.room_ids[0])
                break

    return best_wall, best_t, best_room


def _kmeans(points: list[Point2D], k: int, rng: np.random.Generator) -> list[Point2D]:
    """
    Simple k-means clustering returning k centroids.

    Args:
        points: List of 2D points
        k: Number of clusters
        rng: Random number generator

    Returns:
        List of k centroid points
    """
    if len(points) <= k:
        return points

    # Initialize centers randomly from points
    indices = rng.choice(len(points), k, replace=False)
    centers = [points[i] for i in indices]

    # Iterate until convergence
    max_iterations = 100
    for iteration in range(max_iterations):
        old_centers = [Point2D(c.x, c.y) for c in centers]

        # Assign points to nearest center
        assignments = [0] * len(points)
        for i, p in enumerate(points):
            min_dist = float('inf')
            best_center = 0
            for j, c in enumerate(centers):
                dist = p.distance_to(c)
                if dist < min_dist:
                    min_dist = dist
                    best_center = j
            assignments[i] = best_center

        # Recompute centers
        new_centers = []
        for j in range(k):
            cluster_points = [points[i] for i in range(len(points)) if assignments[i] == j]
            if cluster_points:
                cx = sum(p.x for p in cluster_points) / len(cluster_points)
                cy = sum(p.y for p in cluster_points) / len(cluster_points)
                new_centers.append(Point2D(cx, cy))
            else:
                new_centers.append(centers[j])
        centers = new_centers

        # Check convergence
        converged = all(
            old_centers[j].distance_to(centers[j]) < 1e-6 for j in range(k)
        )
        if converged:
            break

    return centers


def _wall_point(wall: WallSegment, t: float, z: float) -> Point3D:
    """
    Interpolate point along wall segment at fraction t, at height z.

    Args:
        wall: Wall segment
        t: Fraction along wall [0, 1]
        z: Height in meters

    Returns:
        Point3D on the wall at given height
    """
    x = wall.start.x + t * (wall.end.x - wall.start.x)
    y = wall.start.y + t * (wall.end.y - wall.start.y)
    return Point3D(x, y, z)


def _distribute_on_walls(
    room,
    floor,
    count: int,
    height_m: float,
    min_spacing_m: float,
) -> list[tuple[str, float]]:
    """
    Distribute count sensors evenly along the room's walls.

    Args:
        room: Room object
        floor: Floor object (for wall access)
        count: Number of sensors to place
        height_m: Height to place sensors
        min_spacing_m: Minimum spacing between sensors

    Returns:
        List of (wall_id, t) tuples indicating sensor positions
    """
    positions = []

    # Get walls for this room
    walls = [wall for wall in floor.walls if wall.id in room.wall_ids]
    if not walls:
        return positions

    # Compute total wall length
    total_length = sum(wall.start.distance_to(wall.end) for wall in walls)
    if total_length < 1e-6:
        return positions

    # Distribute count sensors along walls
    spacing = total_length / (count + 1) if count > 0 else 0
    current_distance = spacing
    sensor_index = 0

    cumulative_length = 0
    for wall in walls:
        wall_length = wall.start.distance_to(wall.end)
        wall_end_distance = cumulative_length + wall_length

        while current_distance < wall_end_distance and sensor_index < count:
            # Position along this wall
            dist_along_wall = current_distance - cumulative_length
            t = dist_along_wall / wall_length if wall_length > 1e-6 else 0.5
            positions.append((wall.id, t))
            sensor_index += 1
            current_distance += spacing

        cumulative_length = wall_end_distance

    return positions
