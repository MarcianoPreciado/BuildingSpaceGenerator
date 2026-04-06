"""Device placement engine."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from buildingspacegen.core.device import Device, DevicePlacement, PlacementRules, RadioProfile
from buildingspacegen.core.enums import DeviceType, RoomType
from buildingspacegen.core.geometry import Point2D, Point3D
from buildingspacegen.core.model import Building, Floor, Room, WallSegment

from .rules import get_wall_mount_offset

_EPS = 1e-9
_DEVICE_EDGE_CLEARANCE_M = 0.15


@dataclass(frozen=True)
class _WallMount:
    wall: WallSegment
    room: Room
    position_along_wall: float
    mounted_side: str
    point2d: Point2D


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
    wall_mount_offset_m = get_wall_mount_offset(rules)
    devices: list[Device] = []
    device_counter = [0]

    def new_id() -> str:
        device_counter[0] += 1
        return f"dev_{device_counter[0]:04d}"

    def build_device(
        dtype: DeviceType,
        mount: _WallMount,
        height_m: float,
        radio_profile: RadioProfile,
    ) -> Device:
        return Device(
            id=new_id(),
            device_type=dtype,
            position=mount.point2d.to_3d(height_m),
            room_id=mount.room.id,
            wall_id=mount.wall.id,
            radio_profile=radio_profile,
            position_along_wall=mount.position_along_wall,
            mounted_side=mount.mounted_side,
            offset_from_wall_m=wall_mount_offset_m,
        )

    total_sqft = building.total_area_sqft

    mc_count = max(1, math.ceil(total_sqft * rules.main_controller_per_sqft))
    mc_profile = radio_profiles.get(DeviceType.MAIN_CONTROLLER)
    if mc_count == 1 and rules.main_controller_prefer_center:
        mount = _find_wall_closest_to_point(building, building.footprint.centroid(), wall_mount_offset_m)
        if mount is not None:
            devices.append(build_device(DeviceType.MAIN_CONTROLLER, mount, rules.main_controller_wall_height_m, mc_profile))
    else:
        all_rooms = [r for r in building.all_rooms() if r.room_type != RoomType.CORRIDOR]
        if not all_rooms:
            all_rooms = list(building.all_rooms())
        centers = _kmeans([room.polygon.centroid() for room in all_rooms], mc_count, rng)
        for center in centers:
            mount = _find_wall_closest_to_point(building, center, wall_mount_offset_m)
            if mount is not None:
                devices.append(build_device(DeviceType.MAIN_CONTROLLER, mount, rules.main_controller_wall_height_m, mc_profile))

    sc_count = max(1, math.ceil(total_sqft * rules.secondary_controller_per_sqft))
    sc_profile = radio_profiles.get(DeviceType.SECONDARY_CONTROLLER)
    existing_positions = [device.position for device in devices]
    for _ in range(sc_count):
        mount = _find_farthest_wall_position(building, existing_positions, rules.secondary_controller_wall_height_m, wall_mount_offset_m)
        if mount is None:
            continue
        device = build_device(DeviceType.SECONDARY_CONTROLLER, mount, rules.secondary_controller_wall_height_m, sc_profile)
        devices.append(device)
        existing_positions.append(device.position)

    sensor_profile = radio_profiles.get(DeviceType.SENSOR)
    for floor in building.floors:
        for room in floor.rooms:
            if room.room_type in rules.excluded_room_types:
                continue
            count = max(rules.sensor_min_per_room, math.ceil(room.area_sqft * rules.sensor_per_sqft))
            mounts = _distribute_on_walls(
                room=room,
                floor=floor,
                count=count,
                min_spacing_m=rules.sensor_min_spacing_m,
                wall_mount_offset_m=wall_mount_offset_m,
                rng=rng,
            )
            for mount in mounts:
                devices.append(build_device(DeviceType.SENSOR, mount, rules.sensor_wall_height_m, sensor_profile))

    return DevicePlacement(
        building_seed=building.seed,
        devices=devices,
        placement_rules=rules,
    )


def _find_wall_closest_to_point(
    building: Building,
    point: Point2D,
    wall_mount_offset_m: float,
) -> _WallMount | None:
    """Find the wall mount whose interior point is closest to a target point."""
    best_mount = None
    best_score = float("inf")

    for wall in building.all_walls():
        t = _project_point_onto_wall(point, wall)
        t = _clamp_t_with_clearance(wall, t, _DEVICE_EDGE_CLEARANCE_M)
        for room_id in wall.room_ids:
            if room_id is None:
                continue
            room = building.get_room(room_id)
            mount = _mount_for_room(wall, room, t, wall_mount_offset_m)
            if mount is None:
                continue
            room_penalty = 2.0 if room.room_type == RoomType.CORRIDOR else 0.0
            score = point.distance_to(mount.point2d) + room_penalty
            if score < best_score:
                best_mount = mount
                best_score = score

    return best_mount


def _find_farthest_wall_position(
    building: Building,
    existing_positions: list[Point3D],
    height_m: float,
    wall_mount_offset_m: float,
) -> _WallMount | None:
    """Find a wall-mounted point that maximizes minimum distance to existing devices."""
    best_mount = None
    max_min_distance = -1.0

    candidates = []
    for room in building.all_rooms():
        if room.room_type in {RoomType.CORRIDOR, RoomType.ELEVATOR, RoomType.STAIRWELL}:
            continue
        candidates.append(room.polygon.centroid())

    for point in candidates:
        mount = _find_wall_closest_to_point(building, point, wall_mount_offset_m)
        if mount is None:
            continue
        position = mount.point2d.to_3d(height_m)
        min_distance = min((position.distance_to(other) for other in existing_positions), default=float("inf"))
        if min_distance > max_min_distance:
            best_mount = mount
            max_min_distance = min_distance

    return best_mount


def _kmeans(points: list[Point2D], k: int, rng: np.random.Generator) -> list[Point2D]:
    """Simple k-means clustering returning k centroids."""
    if len(points) <= k:
        return points

    indices = rng.choice(len(points), k, replace=False)
    centers = [points[i] for i in indices]

    for _ in range(100):
        old_centers = [Point2D(center.x, center.y) for center in centers]
        assignments = [0] * len(points)

        for idx, point in enumerate(points):
            min_dist = float("inf")
            best_center = 0
            for center_idx, center in enumerate(centers):
                dist = point.distance_to(center)
                if dist < min_dist:
                    min_dist = dist
                    best_center = center_idx
            assignments[idx] = best_center

        new_centers = []
        for center_idx in range(k):
            cluster = [points[idx] for idx in range(len(points)) if assignments[idx] == center_idx]
            if cluster:
                new_centers.append(
                    Point2D(
                        sum(point.x for point in cluster) / len(cluster),
                        sum(point.y for point in cluster) / len(cluster),
                    )
                )
            else:
                new_centers.append(centers[center_idx])
        centers = new_centers

        if all(old_centers[idx].distance_to(centers[idx]) < 1e-6 for idx in range(k)):
            break

    return centers


def _distribute_on_walls(
    room: Room,
    floor: Floor,
    count: int,
    min_spacing_m: float,
    wall_mount_offset_m: float,
    rng: np.random.Generator,
) -> list[_WallMount]:
    """Distribute a room's sensors across its valid walls."""
    if count <= 0:
        return []

    candidate_walls: list[tuple[WallSegment, str]] = []
    for wall in floor.walls:
        if wall.id not in room.wall_ids:
            continue
        side = _mounted_side_for_room(wall, room)
        if side is None:
            continue
        probe = _mount_for_room(wall, room, 0.5, wall_mount_offset_m)
        if probe is None:
            continue
        candidate_walls.append((wall, side))

    if not candidate_walls:
        return []

    allocations: dict[str, int] = {wall.id: 0 for wall, _ in candidate_walls}
    capacities = {
        wall.id: _wall_sensor_capacity(wall, min_spacing_m)
        for wall, _ in candidate_walls
    }

    while sum(allocations.values()) < count:
        eligible = [(wall, side) for wall, side in candidate_walls if allocations[wall.id] < capacities[wall.id]]
        if not eligible:
            break
        wall, _ = max(
            eligible,
            key=lambda item: _wall_length(item[0]) / (allocations[item[0].id] + 1) + float(rng.uniform(0.0, 0.01)),
        )
        allocations[wall.id] += 1

    mounts: list[_WallMount] = []
    for wall, _ in candidate_walls:
        per_wall_count = allocations[wall.id]
        if per_wall_count <= 0:
            continue
        for t in _sample_wall_positions(wall, per_wall_count, min_spacing_m, rng):
            mount = _mount_for_room(wall, room, t, wall_mount_offset_m)
            if mount is not None:
                mounts.append(mount)

    mounts.sort(key=lambda mount: (mount.wall.id, round(mount.position_along_wall, 6)))
    return mounts


def _sample_wall_positions(
    wall: WallSegment,
    count: int,
    min_spacing_m: float,
    rng: np.random.Generator,
) -> list[float]:
    """Sample deterministic-but-random legal positions along a wall."""
    wall_length = _wall_length(wall)
    if wall_length < _EPS:
        return [0.5] * count

    edge_clearance_m = min(_DEVICE_EDGE_CLEARANCE_M, max(0.05, wall_length / 4.0))
    start = edge_clearance_m
    end = max(start, wall_length - edge_clearance_m)
    usable_length = end - start

    if count == 1 or usable_length <= _EPS:
        if usable_length <= _EPS:
            return [0.5]
        distance = float(rng.uniform(start, end))
        return [distance / wall_length]

    required_spacing = min_spacing_m * (count - 1)
    if required_spacing >= usable_length - _EPS:
        distances = np.linspace(start, end, count)
    else:
        slack = usable_length - required_spacing
        gaps = rng.dirichlet(np.ones(count + 1)) * slack
        distances = []
        cursor = start + gaps[0]
        for idx in range(count):
            distances.append(cursor)
            cursor += min_spacing_m
            if idx + 1 < count:
                cursor += gaps[idx + 1]

    return [float(distance / wall_length) for distance in distances]


def _wall_sensor_capacity(wall: WallSegment, min_spacing_m: float) -> int:
    """Return the number of sensors a wall can host while respecting min spacing."""
    wall_length = _wall_length(wall)
    if wall_length < _EPS:
        return 1
    edge_clearance_m = min(_DEVICE_EDGE_CLEARANCE_M, max(0.05, wall_length / 4.0))
    usable_length = max(0.0, wall_length - 2.0 * edge_clearance_m)
    if usable_length < _EPS:
        return 1
    return max(1, int(math.floor(usable_length / max(min_spacing_m, _EPS))) + 1)


def _project_point_onto_wall(point: Point2D, wall: WallSegment) -> float:
    """Project a point onto the wall line and return the clamped fractional parameter."""
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    wall_len_sq = dx * dx + dy * dy
    if wall_len_sq < _EPS:
        return 0.5
    return max(0.0, min(1.0, ((point.x - wall.start.x) * dx + (point.y - wall.start.y) * dy) / wall_len_sq))


def _clamp_t_with_clearance(wall: WallSegment, t: float, edge_clearance_m: float) -> float:
    """Clamp a wall fraction away from both corners when possible."""
    wall_length = _wall_length(wall)
    if wall_length < _EPS:
        return 0.5
    clearance_fraction = min(0.45, edge_clearance_m / wall_length)
    return max(clearance_fraction, min(1.0 - clearance_fraction, t))


def _mount_for_room(
    wall: WallSegment,
    room: Room,
    t: float,
    wall_mount_offset_m: float,
) -> _WallMount | None:
    """Return a legal wall mount for a room/wall pair."""
    if room.id not in wall.room_ids:
        return None

    mounted_side = _mounted_side_for_room(wall, room)
    if mounted_side is None:
        return None

    t = _clamp_t_with_clearance(wall, t, _DEVICE_EDGE_CLEARANCE_M)
    for scale in (1.0, 0.5, 0.25, 0.1, 0.02):
        point = _wall_mount_point(wall, t, mounted_side, wall_mount_offset_m * scale)
        if room.polygon.contains(point):
            return _WallMount(
                wall=wall,
                room=room,
                position_along_wall=t,
                mounted_side=mounted_side,
                point2d=point,
            )

    return None


def _mounted_side_for_room(wall: WallSegment, room: Room) -> str | None:
    """Infer whether a room is on the left or right side of a wall."""
    center = room.polygon.centroid()
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    side_value = dx * (center.y - wall.start.y) - dy * (center.x - wall.start.x)
    if side_value > _EPS:
        return "left"
    if side_value < -_EPS:
        return "right"
    if wall.room_ids[0] == room.id:
        return "left"
    if wall.room_ids[1] == room.id:
        return "right"
    return None


def _wall_mount_point(
    wall: WallSegment,
    t: float,
    mounted_side: str,
    offset_m: float,
) -> Point2D:
    """Return the 2D mounting point slightly inset from the wall centerline."""
    wall_point = _point_on_wall(wall, t)
    _, _, normal_x, normal_y = _wall_basis(wall)
    sign = 1.0 if mounted_side == "left" else -1.0
    return Point2D(
        wall_point.x + sign * normal_x * offset_m,
        wall_point.y + sign * normal_y * offset_m,
    )


def _point_on_wall(wall: WallSegment, t: float) -> Point2D:
    """Interpolate a point along a wall."""
    return Point2D(
        wall.start.x + t * (wall.end.x - wall.start.x),
        wall.start.y + t * (wall.end.y - wall.start.y),
    )


def _wall_basis(wall: WallSegment) -> tuple[float, float, float, float]:
    """Return wall tangent and left-normal unit vectors."""
    dx = wall.end.x - wall.start.x
    dy = wall.end.y - wall.start.y
    length = math.hypot(dx, dy)
    if length < _EPS:
        return 1.0, 0.0, 0.0, 1.0
    tangent_x = dx / length
    tangent_y = dy / length
    normal_x = -tangent_y
    normal_y = tangent_x
    return tangent_x, tangent_y, normal_x, normal_y


def _wall_length(wall: WallSegment) -> float:
    """Return wall length in meters."""
    return wall.start.distance_to(wall.end)
