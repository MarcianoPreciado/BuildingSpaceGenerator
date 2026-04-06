"""Layout helper functions extracted from the BSP generator."""
from __future__ import annotations

from typing import Any

try:
    from core.enums import BuildingType, RoomType
    from buildinggen.archetypes.archetype import RoomProgram
except ImportError:
    from ...core.enums import BuildingType, RoomType
    from ..archetypes.archetype import RoomProgram


EPS = 1e-6
MAX_ROOM_ASPECT_RATIO = 2.0
MIN_ROOM_FRONTAGE_M = 2.2


def front_side(bounds: Any) -> str:
    """Return the primary frontage side for a bounds rectangle."""
    return "south" if bounds.width() >= bounds.height() else "west"


def frontage_side(parcel: Any) -> str:
    """Return the side of the parcel that should receive frontage."""
    candidates = parcel.corridor_sides or parcel.perimeter_sides or ["south"]
    return max(candidates, key=lambda side: frontage_length(parcel.rect, side))


def frontage_length(rect: Any, frontage_side_name: str) -> float:
    """Return the length available along the chosen frontage side."""
    return rect.width() if frontage_side_name in ("north", "south") else rect.height()


def orthogonal_depth(rect: Any, frontage_side_name: str) -> float:
    """Return the depth orthogonal to the frontage side."""
    return rect.height() if frontage_side_name in ("north", "south") else rect.width()


def room_aspect_ratio(rect: Any) -> float:
    """Return the longer-to-shorter side ratio for a rectangular room."""
    width = rect.width()
    height = rect.height()
    shortest = min(width, height)
    if shortest <= EPS:
        return float("inf")
    return max(width, height) / shortest


def _rects_touch(rect_a: Any, rect_b: Any) -> bool:
    """Return whether two axis-aligned rectangles share a full edge."""
    horizontal_touch = (
        abs(rect_a.max_x - rect_b.min_x) < EPS or abs(rect_a.min_x - rect_b.max_x) < EPS
    ) and max(0.0, min(rect_a.max_y, rect_b.max_y) - max(rect_a.min_y, rect_b.min_y)) > EPS
    vertical_touch = (
        abs(rect_a.max_y - rect_b.min_y) < EPS or abs(rect_a.min_y - rect_b.max_y) < EPS
    ) and max(0.0, min(rect_a.max_x, rect_b.max_x) - max(rect_a.min_x, rect_b.min_x)) > EPS
    return horizontal_touch or vertical_touch


def merge_rects(rect_a: Any, rect_b: Any):
    """Return the axis-aligned rectangle covering two touching rectangles."""
    return rect_a.__class__(
        min(rect_a.min_x, rect_b.min_x),
        min(rect_a.min_y, rect_b.min_y),
        max(rect_a.max_x, rect_b.max_x),
        max(rect_a.max_y, rect_b.max_y),
    )


def merge_thin_parcels(parcels: list[Any], max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO) -> list[Any]:
    """Merge adjacent thin parcels before room assignment."""
    merged = list(parcels)

    while True:
        best_index: tuple[int, int] | None = None
        best_ratio = max_aspect_ratio

        for idx, parcel in enumerate(merged):
            current_ratio = room_aspect_ratio(parcel.rect)
            if current_ratio <= max_aspect_ratio:
                continue

            for other_idx, other in enumerate(merged):
                if idx == other_idx or not _rects_touch(parcel.rect, other.rect):
                    continue

                combined_ratio = room_aspect_ratio(merge_rects(parcel.rect, other.rect))
                if combined_ratio < current_ratio and combined_ratio <= best_ratio:
                    best_ratio = combined_ratio
                    best_index = (idx, other_idx)

        if best_index is None:
            break

        idx, other_idx = best_index
        parcel = merged[idx]
        other = merged[other_idx]
        new_rect = merge_rects(parcel.rect, other.rect)
        new_parcel = parcel.__class__(
            rect=new_rect,
            corridor_sides=sorted(set(parcel.corridor_sides) | set(other.corridor_sides)),
            perimeter_sides=sorted(set(parcel.perimeter_sides) | set(other.perimeter_sides)),
        )

        keep = [p for i, p in enumerate(merged) if i not in {idx, other_idx}]
        keep.append(new_parcel)
        merged = keep

    return merged


def promote_thin_parcels_to_corridors(
    parcels: list[Any],
    corridor_rects: list[Any],
    max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO,
) -> tuple[list[Any], list[Any]]:
    """Move corridor-like parcels out of the room allocation pool."""
    kept = []
    promoted = list(corridor_rects)

    for parcel in parcels:
        if room_aspect_ratio(parcel.rect) > max_aspect_ratio:
            promoted.append(parcel.rect)
        else:
            kept.append(parcel)

    return kept, promoted


def slice_rect(rect: Any, frontage_side_name: str, cursor: float, slice_length: float):
    """Slice a rectangular parcel along its frontage side."""
    if frontage_side_name in ("north", "south"):
        return rect.__class__(cursor, rect.min_y, min(rect.max_x, cursor + slice_length), rect.max_y)
    return rect.__class__(rect.min_x, cursor, rect.max_x, min(rect.max_y, cursor + slice_length))


def bounded_slice_length(
    rect: Any,
    frontage_side_name: str,
    desired_area: float,
    remaining_length: float,
    min_frontage: float = MIN_ROOM_FRONTAGE_M,
    max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO,
) -> float:
    """Choose a slice length that keeps the resulting rectangle near the aspect target."""
    if remaining_length <= 0.0:
        return 0.0

    depth = orthogonal_depth(rect, frontage_side_name)
    if depth <= EPS:
        return remaining_length

    target_length = desired_area / depth
    min_length = max(min_frontage, depth / max_aspect_ratio)
    max_length = max(min_length, depth * max_aspect_ratio)

    if remaining_length < min_length:
        return remaining_length

    return min(remaining_length, max(min_length, min(target_length, max_length)))


def bounded_split_length(
    rect: Any,
    frontage_side_name: str,
    desired_area: float,
    max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO,
    min_frontage: float = MIN_ROOM_FRONTAGE_M,
) -> float:
    """Choose a split point for a room slice while favoring the target aspect ratio."""
    depth = orthogonal_depth(rect, frontage_side_name)
    frontage = frontage_length(rect, frontage_side_name)
    if depth <= EPS or frontage <= EPS:
        return frontage * 0.5

    target_length = desired_area / depth
    min_length = max(min_frontage, depth / max_aspect_ratio)
    max_length = min(frontage - min_frontage, depth * max_aspect_ratio)

    if max_length < min_length:
        return min(frontage - min_frontage, max(min_frontage, target_length))

    return min(max_length, max(min_length, target_length))


def rebalance_small_trailing_rooms(
    parcel: Any,
    room_program: dict[RoomType, RoomProgram],
    max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO,
) -> None:
    """Merge a too-small or too-thin trailing room slice back into the previous room."""
    if len(parcel.assigned_rooms) < 2:
        return

    room_type, rect = parcel.assigned_rooms[-1]
    program = room_program.get(room_type)
    if program is None:
        return

    too_small = rect.area() < program.min_area_sqm * 0.8
    too_thin = room_aspect_ratio(rect) > max_aspect_ratio
    if not too_small and not too_thin:
        return

    prev_type, prev_rect = parcel.assigned_rooms[-2]
    if abs(prev_rect.max_x - rect.min_x) < EPS and abs(prev_rect.min_y - rect.min_y) < EPS and abs(prev_rect.max_y - rect.max_y) < EPS:
        merged = rect.__class__(prev_rect.min_x, prev_rect.min_y, rect.max_x, rect.max_y)
    elif abs(prev_rect.max_y - rect.min_y) < EPS and abs(prev_rect.min_x - rect.min_x) < EPS and abs(prev_rect.max_x - rect.max_x) < EPS:
        merged = rect.__class__(prev_rect.min_x, prev_rect.min_y, rect.max_x, rect.max_y)
    else:
        return

    parcel.assigned_rooms[-2] = (prev_type, merged)
    parcel.assigned_rooms.pop()


def rebalance_thin_rooms(
    parcel: Any,
    room_program: dict[RoomType, RoomProgram],
    max_aspect_ratio: float = MAX_ROOM_ASPECT_RATIO,
) -> None:
    """Convert thin support rooms into circulation instead of keeping corridor-like rectangles."""
    rebounded = []

    for room_type, rect in parcel.assigned_rooms:
        program = room_program.get(room_type)
        if program is None or room_aspect_ratio(rect) <= max_aspect_ratio:
            rebounded.append((room_type, rect))
            continue

        if room_type == RoomType.OPEN_OFFICE:
            if room_aspect_ratio(rect) <= max_aspect_ratio * 2.0:
                rebounded.append((room_type, rect))
            else:
                rebounded.append((RoomType.CORRIDOR, rect))
            continue

        rebounded.append((RoomType.CORRIDOR, rect))

    parcel.assigned_rooms = rebounded


def room_score(
    room_type: RoomType,
    parcel: Any,
    bounds: Any,
    front_side_name: str,
    building_type: BuildingType,
) -> float:
    """Score a parcel for a particular room type."""
    center = parcel.rect.center()
    bounds_center = bounds.center()
    dx = abs(center.x - bounds_center.x) / max(bounds.width(), 1.0)
    dy = abs(center.y - bounds_center.y) / max(bounds.height(), 1.0)
    centrality = 1.0 - min(1.0, (dx * dx + dy * dy) ** 0.5 * 1.8)
    edge_exposure = len(parcel.perimeter_sides) / 4.0
    corridor_access = len(parcel.corridor_sides) / 4.0
    frontness_score = frontness(parcel.rect, bounds, front_side_name)
    parcel_area = parcel.rect.area()
    large_parcel = min(parcel_area / max(bounds.area(), 1.0) * 8.0, 1.0)
    parcel_aspect = room_aspect_ratio(parcel.rect)
    aspect_bonus = 1.0 - min(1.0, max(0.0, parcel_aspect - MAX_ROOM_ASPECT_RATIO) / MAX_ROOM_ASPECT_RATIO)
    aspect_penalty = max(0.0, parcel_aspect - MAX_ROOM_ASPECT_RATIO) / MAX_ROOM_ASPECT_RATIO
    shape_adjustment = 0.10 * aspect_bonus - 0.30 * aspect_penalty

    if room_type == RoomType.OPEN_OFFICE:
        return 0.45 * edge_exposure + 0.25 * (1.0 - centrality) + 0.20 * corridor_access + 0.15 * large_parcel + shape_adjustment
    if room_type == RoomType.WAREHOUSE_BAY:
        return 0.60 * (1.0 - frontness_score) + 0.20 * edge_exposure + 0.25 * large_parcel + shape_adjustment
    if room_type == RoomType.PRIVATE_OFFICE:
        return 0.35 * edge_exposure + 0.30 * corridor_access + 0.20 * centrality + shape_adjustment
    if room_type == RoomType.CONFERENCE:
        return 0.35 * centrality + 0.20 * edge_exposure + 0.25 * corridor_access + 0.15 * frontness_score + shape_adjustment
    if room_type == RoomType.LOBBY:
        return 0.55 * frontness_score + 0.25 * edge_exposure + 0.20 * centrality + shape_adjustment
    if room_type == RoomType.LOADING_DOCK:
        return 0.60 * frontness_score + 0.25 * edge_exposure + 0.15 * corridor_access + shape_adjustment
    if room_type in {RoomType.RESTROOM, RoomType.MECHANICAL, RoomType.IT_SERVER, RoomType.STAIRWELL, RoomType.ELEVATOR, RoomType.STORAGE}:
        return 0.50 * centrality + 0.30 * corridor_access + 0.10 * (1.0 - edge_exposure) + shape_adjustment
    if room_type == RoomType.KITCHEN_BREAK:
        return 0.35 * centrality + 0.25 * edge_exposure + 0.25 * corridor_access + shape_adjustment

    return 0.25 * corridor_access + 0.20 * edge_exposure + 0.20 * centrality + shape_adjustment


def frontness(rect: Any, bounds: Any, front_side_name: str) -> float:
    """Return a frontness score for the current frontage side."""
    if front_side_name == "south":
        return 1.0 - ((rect.center().y - bounds.min_y) / max(bounds.height(), 1.0))
    if front_side_name == "north":
        return (rect.center().y - bounds.min_y) / max(bounds.height(), 1.0)
    if front_side_name == "west":
        return 1.0 - ((rect.center().x - bounds.min_x) / max(bounds.width(), 1.0))
    return (rect.center().x - bounds.min_x) / max(bounds.width(), 1.0)


def is_outer_parcel(parcel: Any, bounds: Any) -> bool:
    """Return whether the parcel is on the building outer ring."""
    return bool(parcel.perimeter_sides) or (
        abs(parcel.rect.center().x - bounds.center().x) / max(bounds.width(), 1.0)
        + abs(parcel.rect.center().y - bounds.center().y) / max(bounds.height(), 1.0)
    ) > 0.35
