"""Tests for the Quantum graph importer bridge."""
import math

from buildingspacegen.core.enums import BuildingType
from buildingspacegen.sources.quantum.importer import list_quantum_floors, load_quantum_floor


KAJIMA_GRAPH = "Sample Buildings/Kajima 11th Floor/Kajima 11th Floor.graph.json"
PANASONIC_GRAPH = "Sample Buildings/Panasonic - Site 4/Panasonic - Site 4.graph.json"
_EPS = 1e-6


def _point_on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> bool:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= _EPS:
        return math.hypot(px - sx, py - sy) <= _EPS

    cross = (px - sx) * dy - (py - sy) * dx
    if abs(cross) > _EPS:
        return False

    dot = (px - sx) * dx + (py - sy) * dy
    if dot < -_EPS or dot > seg_len_sq + _EPS:
        return False

    return True


def _segment_matches_room_boundary(room, wall) -> bool:
    vertices = room.polygon.vertices
    wall_start = (wall.start.x, wall.start.y)
    wall_end = (wall.end.x, wall.end.y)
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        edge_start = (start.x, start.y)
        edge_end = (end.x, end.y)
        if _point_on_segment(wall_start, edge_start, edge_end) and _point_on_segment(wall_end, edge_start, edge_end):
            return True
    return False


def test_list_quantum_floors_kajima_exposes_floor_zero() -> None:
    floors = list_quantum_floors(KAJIMA_GRAPH)

    assert floors
    assert floors[0].name == "Floor 0"
    assert floors[0].level == 0
    assert floors[0].zone_count == 42
    assert floors[0].is_default_candidate is True


def test_load_quantum_floor_kajima_preserves_floor_metadata() -> None:
    building = load_quantum_floor(KAJIMA_GRAPH, floor_selector="Floor 0", seed=17)

    assert building.building_type == BuildingType.MEDIUM_OFFICE
    assert building.metadata["source_floor_name"] == "Floor 0"
    assert building.metadata["source_site_name"] == "Kajima 11th Floor"
    assert building.metadata["source_site_directory"] == "Kajima"
    assert building.metadata["source_location_latitude"] == 34.69394578756324
    assert building.metadata["source_location_longitude"] == 135.53273584794596
    assert building.metadata["source_building_owner_name"] is None
    assert len(building.floors) == 1
    assert len(building.floors[0].rooms) == 42
    assert len(building.floors[0].walls) > len(building.floors[0].rooms)
    assert len(building.floors[0].doors) > 0

    room_names = {room.metadata.get("display_name") for room in building.floors[0].rooms}
    assert "Conference Room 1" in room_names
    assert "Office 1" in room_names


def test_load_quantum_floor_kajima_infers_window_sides() -> None:
    building = load_quantum_floor(KAJIMA_GRAPH, floor_selector="Floor 0", seed=17)
    rooms = {room.metadata.get("display_name"): room for room in building.floors[0].rooms}

    conference_room = rooms["Conference Room 1"]
    assert conference_room.has_windows is True
    assert conference_room.window_sides == ["E", "S"]
    assert conference_room.metadata["has_windows"] is True
    assert conference_room.metadata["window_sides"] == ["E", "S"]

    storage_room = rooms["Storage 5"]
    assert storage_room.has_windows is False
    assert storage_room.window_sides == []


def test_load_quantum_floor_kajima_walls_follow_room_boundaries() -> None:
    building = load_quantum_floor(KAJIMA_GRAPH, floor_selector="Floor 0", seed=17)
    floor = building.floors[0]
    rooms = {room.id: room for room in floor.rooms}

    for wall in floor.walls:
        assert _segment_matches_room_boundary(rooms[wall.room_ids[0]], wall), wall.id


def test_load_quantum_floor_panasonic_floor_two() -> None:
    building = load_quantum_floor(PANASONIC_GRAPH, floor_selector="Floor 2", seed=5)

    assert building.building_type == BuildingType.LARGE_OFFICE
    assert building.metadata["source_floor_name"] == "Floor 2"
    assert len(building.floors[0].rooms) == 73
    assert len(building.floors[0].walls) > 400
    assert len(building.floors[0].doors) > 50

    rooms = {room.metadata.get("display_name"): room for room in building.floors[0].rooms}
    assert rooms["Space 46"].window_sides == ["E", "S"]
    assert rooms["Space 197"].has_windows is False
