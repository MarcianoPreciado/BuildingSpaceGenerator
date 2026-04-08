"""Import Quantum graph exports into the current building compatibility model."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from buildingspacegen.core.enums import BuildingType, RoomType
from buildingspacegen.core.geometry import Point2D, Polygon2D
from buildingspacegen.core.model import Building, Door, Floor, Material, Room, WallSegment


_EPS = 1e-6
_DEFAULT_MATERIAL_THICKNESS_M = {
    "gypsum_single": 0.013,
    "gypsum_double": 0.026,
    "concrete_block": 0.2,
    "reinforced_concrete": 0.2,
    "brick": 0.1,
    "glass_standard": 0.006,
    "glass_low_e": 0.006,
    "wood_door": 0.045,
    "metal_fire_door": 0.05,
    "elevator_shaft": 0.2,
}
_OPENING_SURFACE_TYPES = {"Door", "Glazing", "GarageDoor"}


@dataclass(frozen=True)
class QuantumFloorSummary:
    """Summary of a floor available in a Quantum graph export."""

    id: str
    name: str
    level: int | None
    elevation_m: float | None
    zone_count: int
    is_default_candidate: bool


@dataclass(frozen=True)
class _OpeningInterval:
    kind: str
    start_m: float
    end_m: float
    width_m: float
    height_m: float | None
    material_name: str
    source_surface_id: str


@dataclass(frozen=True)
class _RawEdge:
    room_id: str
    room_type: RoomType
    start: Point2D
    end: Point2D
    explicit_material_name: str | None
    openings: tuple[_OpeningInterval, ...]
    source_surface_id: str | None
    source_wall_name: str | None

    @property
    def length_m(self) -> float:
        return self.start.distance_to(self.end)


class _QuantumGraph:
    """Convenience wrapper around a Quantum graph JSON export."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with open(path) as f:
            self.data = json.load(f)
        self.root = self.data.get("root", {})
        self.root_type = self.data.get("rootType")
        self.metadata = self.data.get("metadata", {})
        self.nodes = self.data.get("nodes", [])
        self.by_id = {
            node["ID"]: node
            for node in self.nodes
            if isinstance(node, dict) and node.get("ID")
        }

    def node(self, node_id: str | None) -> dict[str, Any] | None:
        if not node_id:
            return None
        if node_id == self.root.get("ID"):
            return self.root
        return self.by_id.get(node_id)

    def nodes_of_type(self, typename: str) -> list[dict[str, Any]]:
        return [node for node in self.nodes if node.get("__typename") == typename]

    def property_map(self, node: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        if not node:
            return result
        for property_id in node.get("propertyIDs", []) or []:
            prop = self.node(property_id)
            if prop and prop.get("__typename") == "Property" and prop.get("name"):
                result[prop["name"]] = prop
        return result

    def property_value(self, node: dict[str, Any] | None, name: str, default: Any = None) -> Any:
        prop = self.property_map(node).get(name)
        if prop is None:
            return default
        value = prop.get("currentValue")
        return default if value is None else value


def list_quantum_floors(path: str | Path) -> list[QuantumFloorSummary]:
    """List floors available in a Quantum graph export."""
    graph = _QuantumGraph(path)
    building = _select_building_node(graph)
    summaries = [_floor_summary(graph, graph.node(floor_id)) for floor_id in building.get("floorIDs", []) or []]
    return sorted(summaries, key=_floor_summary_sort_key)


def load_quantum_floor(
    path: str | Path,
    floor_selector: str | int | None = None,
    building_type: BuildingType | None = None,
    seed: int = 42,
) -> Building:
    """Load a selected Quantum floor export into the current Building model."""
    graph = _QuantumGraph(path)
    site_node = _select_site_node(graph)
    building_node = _select_building_node(graph)
    location_node = _select_location_node(graph, site_node, building_node)
    relative_north_deg = _coerce_float(graph.property_value(building_node, "relativeNorth"), default=0.0) or 0.0
    floor_node = _select_floor_node(graph, building_node, floor_selector)
    zone_nodes = _select_floor_zones(graph, floor_node)

    if not zone_nodes:
        raise ValueError(f"Selected floor '{floor_node.get('name')}' does not contain any importable zones")

    room_defs: list[tuple[Room, list[_RawEdge]]] = []
    all_points: list[Point2D] = []
    for zone in zone_nodes:
        room, raw_edges = _build_room(graph, zone, floor_node)
        room_defs.append((room, raw_edges))
        all_points.extend(room.polygon.vertices)

    if not all_points:
        raise ValueError(f"Selected floor '{floor_node.get('name')}' has no importable geometry")

    floor_index = _coerce_int(graph.property_value(floor_node, "level"), default=0)
    floor_height_m = _coerce_float(graph.property_value(floor_node, "height"), default=3.0)
    floor_elevation_m = _coerce_float(graph.property_value(floor_node, "elevation"), default=0.0)
    selected_building_type = building_type or _infer_building_type([room for room, _ in room_defs])

    edge_groups: dict[tuple[tuple[float, float], tuple[float, float]], list[_RawEdge]] = {}
    for _, raw_edges in room_defs:
        for edge in raw_edges:
            edge_groups.setdefault(_segment_key(edge.start, edge.end), []).append(edge)

    wall_counter = 0
    door_counter = 0
    walls: list[WallSegment] = []
    doors: list[Door] = []
    room_lookup = {room.id: room for room, _ in room_defs}
    room_wall_ids: dict[str, list[str]] = {room.id: [] for room, _ in room_defs}
    room_door_ids: dict[str, list[str]] = {room.id: [] for room, _ in room_defs}
    room_window_sides: dict[str, set[str]] = {room.id: set() for room, _ in room_defs}

    for key, group in edge_groups.items():
        if not group:
            continue
        length_m = group[0].length_m
        if length_m <= _EPS:
            continue

        canonical_start, _ = key
        breakpoints = {0.0, length_m}
        group_openings: list[tuple[float, float, _OpeningInterval]] = []
        for edge in group:
            raw_is_canonical = _point_key(edge.start) == canonical_start
            for opening in edge.openings:
                can_start, can_end = _to_canonical_interval(opening.start_m, opening.end_m, length_m, raw_is_canonical)
                breakpoints.add(can_start)
                breakpoints.add(can_end)
                group_openings.append((can_start, can_end, opening))

        ordered_breakpoints = sorted(point for point in breakpoints if 0.0 <= point <= length_m)
        group_room_types = [edge.room_type for edge in group]
        explicit_material_name = next((edge.explicit_material_name for edge in group if edge.explicit_material_name), None)
        is_exterior = len(group) == 1

        for segment_start, segment_end in zip(ordered_breakpoints, ordered_breakpoints[1:]):
            if segment_end - segment_start <= _EPS:
                continue

            opening = _opening_covering_interval(group_openings, segment_start, segment_end)
            if opening is not None:
                material_name = opening.material_name
                opening_kind = opening.kind
                source_surface_id = opening.source_surface_id
                piece_height_m = opening.height_m or 2.1
            else:
                material_name = _infer_solid_wall_material(
                    explicit_material_name=explicit_material_name,
                    is_exterior=is_exterior,
                    room_types=group_room_types,
                )
                opening_kind = None
                source_surface_id = group[0].source_surface_id
                piece_height_m = floor_height_m

            thickness_m = _material_thickness(material_name)
            for edge in group:
                raw_is_canonical = _point_key(edge.start) == canonical_start
                raw_start_m, raw_end_m = _from_canonical_interval(segment_start, segment_end, length_m, raw_is_canonical)
                piece_start = _point_along_edge(edge.start, edge.end, raw_start_m)
                piece_end = _point_along_edge(edge.start, edge.end, raw_end_m)
                if piece_start.distance_to(piece_end) <= _EPS:
                    continue

                wall_counter += 1
                wall_id = f"wall_{wall_counter:05d}"
                wall = WallSegment(
                    id=wall_id,
                    start=piece_start,
                    end=piece_end,
                    height=piece_height_m,
                    materials=[Material(material_name, thickness_m)],
                    is_exterior=is_exterior,
                    room_ids=(edge.room_id, None),
                    metadata={
                        "source_type": "quantum_graph",
                        "source_path": graph.path,
                        "source_surface_id": source_surface_id,
                        "source_wall_surface_id": edge.source_surface_id,
                        "opening_kind": opening_kind,
                    },
                )
                walls.append(wall)
                room_wall_ids[edge.room_id].append(wall_id)
                if opening_kind == "glazing" and is_exterior:
                    room = room_lookup[edge.room_id]
                    side = _window_side_for_segment(
                        piece_start,
                        piece_end,
                        room.polygon,
                        relative_north_deg,
                    )
                    if side is not None:
                        room_window_sides[edge.room_id].add(side)

                if opening_kind in {"door", "garage_door"}:
                    door_counter += 1
                    door_id = f"door_{door_counter:05d}"
                    door = Door(
                        id=door_id,
                        wall_id=wall_id,
                        position_along_wall=0.5,
                        width=piece_start.distance_to(piece_end),
                        height=piece_height_m,
                        material=Material(material_name, thickness_m),
                    )
                    doors.append(door)
                    room_door_ids[edge.room_id].append(door_id)

    rooms: list[Room] = []
    for room, _ in room_defs:
        room.wall_ids = room_wall_ids[room.id]
        room.door_ids = room_door_ids[room.id]
        window_sides = [side for side in ("N", "E", "S", "W") if side in room_window_sides[room.id]]
        room.has_windows = bool(window_sides)
        room.window_sides = window_sides
        room.metadata["has_windows"] = room.has_windows
        room.metadata["window_sides"] = list(window_sides)
        rooms.append(room)

    footprint = _convex_hull_polygon(all_points)
    total_area_sqft = sum(room.area_sqft for room in rooms)

    floor = Floor(
        index=floor_index,
        rooms=rooms,
        walls=walls,
        doors=doors,
        elevation=floor_elevation_m,
        footprint=footprint,
    )

    return Building(
        building_type=selected_building_type,
        floors=[floor],
        footprint=footprint,
        total_area_sqft=total_area_sqft,
        seed=seed,
        metadata={
            "source_type": "quantum_graph",
            "source_path": graph.path,
            "source_version": graph.metadata.get("version"),
            "source_root_type": graph.root_type,
            "source_site_id": graph.root.get("ID"),
            "source_building_id": building_node.get("ID"),
            "source_building_name": building_node.get("name"),
            "source_floor_id": floor_node.get("ID"),
            "source_floor_name": floor_node.get("name"),
            "source_floor_level": floor_index,
            "relative_north_deg": relative_north_deg,
            "available_floors": [
                {
                    "id": summary.id,
                    "name": summary.name,
                    "level": summary.level,
                    "elevation_m": summary.elevation_m,
                    "zone_count": summary.zone_count,
                    "is_default_candidate": summary.is_default_candidate,
                }
                for summary in list_quantum_floors(path)
            ],
            **_high_level_source_metadata(graph, site_node, building_node, floor_node, location_node),
        },
    )


def _select_site_node(graph: _QuantumGraph) -> dict[str, Any] | None:
    if graph.root_type == "Site":
        return graph.root

    building = _select_building_node(graph)
    site_id = building.get("siteID")
    site = graph.node(site_id)
    if site and site.get("__typename") == "Site":
        return site

    sites = graph.nodes_of_type("Site")
    return sites[0] if sites else None


def _select_building_node(graph: _QuantumGraph) -> dict[str, Any]:
    if graph.root_type == "Building":
        return graph.root
    if graph.root_type == "Site":
        for building_id in graph.root.get("buildingIDs", []) or []:
            building = graph.node(building_id)
            if building and building.get("__typename") == "Building":
                return building

    buildings = graph.nodes_of_type("Building")
    if not buildings:
        raise ValueError(f"No Building nodes found in {graph.path}")
    return buildings[0]


def _select_location_node(
    graph: _QuantumGraph,
    site: dict[str, Any] | None,
    building: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if site:
        location = graph.node(site.get("locationID"))
        if location and location.get("__typename") == "Location":
            return location
    if building:
        location = graph.node(building.get("locationID"))
        if location and location.get("__typename") == "Location":
            return location
    return None


def _high_level_source_metadata(
    graph: _QuantumGraph,
    site: dict[str, Any] | None,
    building: dict[str, Any],
    floor: dict[str, Any],
    location: dict[str, Any] | None,
) -> dict[str, Any]:
    building_props = graph.property_map(building)
    floor_props = graph.property_map(floor)

    metadata = {
        "source_site_name": None if site is None else site.get("name"),
        "source_site_directory": None if site is None else site.get("siteDirectory"),
        "source_site_project_state": None if site is None else site.get("projectState"),
        "source_site_status": None if site is None else site.get("status"),
        "source_site_feature_access": None if site is None else site.get("featureAccess"),
        "source_site_campus_id": None if site is None else site.get("campusID"),
        "source_site_image_id": None if site is None else site.get("imageID"),
        "source_building_site_id": building.get("siteID"),
        "source_building_location_id": building.get("locationID"),
        "source_building_image_id": building.get("imageID"),
        "source_building_owner_name": None,
        "source_building_owner_id": None,
        "source_geometry_units": None if "geometryUnits" not in building_props else building_props["geometryUnits"].get("unit"),
        "source_floor_elevation_m": _coerce_float(graph.property_value(floor, "elevation"), default=None),
        "source_floor_height_m": _coerce_float(graph.property_value(floor, "height"), default=None),
        "source_floor_ceiling_height_m": _coerce_float(graph.property_value(floor, "ceilingHeight"), default=None),
        "source_floor_slab_depth_m": _coerce_float(graph.property_value(floor, "floorSlabDepth"), default=None),
    }

    for key in ("groundsmashMinX", "groundsmashMaxX", "groundsmashMinY", "groundsmashMaxY", "groundsmashElevation", "groundsmashRotation", "groundsmashAdjusted"):
        value = graph.property_value(building, key, default=None)
        metadata[f"source_{key}"] = value

    if location is not None:
        metadata.update(
            {
                "source_location_id": location.get("ID"),
                "source_location_name": location.get("name"),
                "source_location_latitude": _coerce_float(location.get("latitude"), default=None),
                "source_location_longitude": _coerce_float(location.get("longitude"), default=None),
                "source_location_elevation": _coerce_float(location.get("elevation"), default=None),
                "source_location_address": location.get("address"),
                "source_location_city": location.get("city"),
                "source_location_state": location.get("state"),
                "source_location_country": location.get("country"),
                "source_location_postal_code": location.get("postalCode"),
            }
        )
    else:
        metadata.update(
            {
                "source_location_id": None,
                "source_location_name": None,
                "source_location_latitude": None,
                "source_location_longitude": None,
                "source_location_elevation": None,
                "source_location_address": None,
                "source_location_city": None,
                "source_location_state": None,
                "source_location_country": None,
                "source_location_postal_code": None,
            }
        )

    return metadata


def _floor_summary(graph: _QuantumGraph, floor: dict[str, Any] | None) -> QuantumFloorSummary:
    if floor is None:
        raise ValueError("Floor summary requested for a missing floor")
    level = _coerce_int(graph.property_value(floor, "level"), default=None)
    elevation_m = _coerce_float(graph.property_value(floor, "elevation"), default=None)
    zone_count = len(_select_floor_zones(graph, floor))
    floor_name = floor.get("name") or floor.get("ID")
    lowered_name = floor_name.lower()
    is_default_candidate = zone_count > 0 and not any(
        token in lowered_name for token in ("roof", "outdoor", "mechanical")
    )
    return QuantumFloorSummary(
        id=floor["ID"],
        name=floor_name,
        level=level,
        elevation_m=elevation_m,
        zone_count=zone_count,
        is_default_candidate=is_default_candidate,
    )


def _floor_summary_sort_key(summary: QuantumFloorSummary) -> tuple[int, float, float, str]:
    preferred = 0 if summary.is_default_candidate else 1
    level_sort = summary.level if summary.level is not None else 10_000
    elevation_sort = summary.elevation_m if summary.elevation_m is not None else 10_000.0
    return (preferred, float(level_sort), float(elevation_sort), summary.name.lower())


def _select_floor_node(
    graph: _QuantumGraph,
    building: dict[str, Any],
    floor_selector: str | int | None,
) -> dict[str, Any]:
    floors = [graph.node(floor_id) for floor_id in building.get("floorIDs", []) or []]
    floors = [floor for floor in floors if floor]
    if not floors:
        raise ValueError(f"No floors available for building {building.get('ID')}")

    summaries = {floor["ID"]: _floor_summary(graph, floor) for floor in floors}
    sorted_floors = sorted(floors, key=lambda floor: _floor_summary_sort_key(summaries[floor["ID"]]))

    if floor_selector is None:
        for floor in sorted_floors:
            if summaries[floor["ID"]].is_default_candidate:
                return floor
        return sorted_floors[0]

    if isinstance(floor_selector, int):
        for floor in floors:
            if summaries[floor["ID"]].level == floor_selector:
                return floor
        if 0 <= floor_selector < len(sorted_floors):
            return sorted_floors[floor_selector]
        raise ValueError(f"Could not find floor selector {floor_selector} in {graph.path}")

    selector = str(floor_selector).strip()
    if selector.isdigit():
        return _select_floor_node(graph, building, int(selector))
    lowered_selector = selector.lower()

    for floor in floors:
        if floor["ID"] == selector:
            return floor
    for floor in floors:
        if (floor.get("name") or "").lower() == lowered_selector:
            return floor

    available = [floor.get("name") or floor.get("ID") for floor in sorted_floors]
    raise ValueError(f"Could not find floor '{selector}' in {graph.path}. Available floors: {available}")


def _select_floor_zones(graph: _QuantumGraph, floor: dict[str, Any]) -> list[dict[str, Any]]:
    zones = [graph.node(zone_id) for zone_id in floor.get("zoneIDs", []) or []]
    zones = [zone for zone in zones if zone and zone.get("__typename") == "Zone"]
    return [zone for zone in zones if _zone_boundary_surface(graph, zone) is not None]


def _zone_boundary_surface(graph: _QuantumGraph, zone: dict[str, Any]) -> dict[str, Any] | None:
    for surface_id in zone.get("surfaceIDs", []) or []:
        surface = graph.node(surface_id)
        if surface and surface.get("surfaceType") == "Boundary" and surface.get("shapeIDs"):
            return surface
    return None


def _build_room(
    graph: _QuantumGraph,
    zone: dict[str, Any],
    floor: dict[str, Any],
) -> tuple[Room, list[_RawEdge]]:
    boundary = _zone_boundary_surface(graph, zone)
    if boundary is None:
        raise ValueError(f"Zone {zone.get('ID')} has no boundary surface")

    shape = graph.node(boundary["shapeIDs"][0])
    if shape is None:
        raise ValueError(f"Boundary surface {boundary.get('ID')} has no shape")

    ordered_shape_vertices = [graph.node(vertex_id) for vertex_id in shape.get("vertexIDs", []) or []]
    ordered_shape_vertices = [vertex for vertex in ordered_shape_vertices if vertex]
    ordered_shape_vertices.sort(key=lambda vertex: vertex.get("index", 0))
    polygon = Polygon2D([Point2D(float(vertex["x"]), float(vertex["y"])) for vertex in ordered_shape_vertices])

    zone_name = zone.get("name") or f"Zone {zone.get('ID')}"
    area_sqm = _coerce_float(graph.property_value(zone, "area"), default=polygon.area()) or polygon.area()
    room_type = _infer_room_type(zone_name, area_sqm)
    ceiling_height = _coerce_float(
        graph.property_value(zone, "ceilingHeight"),
        default=_coerce_float(graph.property_value(zone, "height"), default=_coerce_float(graph.property_value(floor, "height"), default=3.0)),
    ) or 3.0

    room_id = f"room_{zone['ID']}"
    room = Room(
        id=room_id,
        room_type=room_type,
        polygon=polygon,
        floor_index=_coerce_int(graph.property_value(floor, "level"), default=0) or 0,
        wall_ids=[],
        door_ids=[],
        ceiling_height=ceiling_height,
        metadata={
            "source_type": "quantum_graph",
            "source_zone_id": zone["ID"],
            "source_name": zone_name,
            "display_name": zone_name,
            "classification": room_type.value,
            "source_color": zone.get("color"),
            "area_sqm_source": area_sqm,
        },
    )

    wall_surfaces: dict[str, dict[str, Any]] = {}
    for surface_id in zone.get("surfaceIDs", []) or []:
        surface = graph.node(surface_id)
        if surface and surface.get("surfaceType") == "Wall":
            vertex_ids = surface.get("vertexIDs", []) or []
            if vertex_ids:
                wall_surfaces[vertex_ids[0]] = surface

    raw_edges: list[_RawEdge] = []
    ordered_shape_vertex_ids = [vertex["ID"] for vertex in ordered_shape_vertices]
    for index, start_vertex_id in enumerate(ordered_shape_vertex_ids):
        start_vertex = ordered_shape_vertices[index]
        end_vertex = ordered_shape_vertices[(index + 1) % len(ordered_shape_vertices)]

        start = Point2D(float(start_vertex["x"]), float(start_vertex["y"]))
        end = Point2D(float(end_vertex["x"]), float(end_vertex["y"]))
        wall_surface = wall_surfaces.get(start_vertex_id)
        raw_edges.append(
            _RawEdge(
                room_id=room_id,
                room_type=room_type,
                start=start,
                end=end,
                explicit_material_name=_material_from_surface_construction(graph, wall_surface),
                openings=tuple(_extract_openings_for_wall(graph, wall_surface, start, end, room_type)),
                source_surface_id=None if wall_surface is None else wall_surface.get("ID"),
                source_wall_name=None if wall_surface is None else wall_surface.get("name"),
            )
        )

    return room, raw_edges


def _extract_openings_for_wall(
    graph: _QuantumGraph,
    wall_surface: dict[str, Any] | None,
    start: Point2D,
    end: Point2D,
    room_type: RoomType,
) -> list[_OpeningInterval]:
    if wall_surface is None:
        return []

    dx = end.x - start.x
    dy = end.y - start.y
    length_m = math.hypot(dx, dy)
    if length_m <= _EPS:
        return []

    tangent_x = dx / length_m
    tangent_y = dy / length_m
    openings: list[_OpeningInterval] = []
    for adjacency_id in wall_surface.get("parentAdjacencyIDs", []) or []:
        adjacency = graph.node(adjacency_id)
        if adjacency is None:
            continue

        child_surface = graph.node(adjacency.get("childSurfaceID"))
        if child_surface is None or child_surface.get("surfaceType") not in _OPENING_SURFACE_TYPES:
            continue

        width_m = _coerce_float(
            graph.property_value(child_surface, "width"),
            default=_coerce_float(graph.property_value(child_surface, "length"), default=0.0),
        ) or 0.0
        if width_m <= _EPS:
            continue

        offset_x = _coerce_float(adjacency.get("x"), default=0.0) or 0.0
        offset_y = _coerce_float(adjacency.get("y"), default=0.0) or 0.0
        start_m = max(0.0, min(length_m, offset_x * tangent_x + offset_y * tangent_y))
        end_m = max(start_m, min(length_m, start_m + width_m))
        if end_m - start_m <= _EPS:
            continue

        openings.append(
            _OpeningInterval(
                kind=_opening_kind(child_surface),
                start_m=start_m,
                end_m=end_m,
                width_m=end_m - start_m,
                height_m=_coerce_float(graph.property_value(child_surface, "height"), default=None),
                material_name=_infer_opening_material(child_surface, room_type),
                source_surface_id=child_surface["ID"],
            )
        )

    openings.sort(key=lambda opening: (opening.start_m, opening.end_m))
    return openings


def _material_from_surface_construction(graph: _QuantumGraph, surface: dict[str, Any] | None) -> str | None:
    if surface is None:
        return None
    layer_set = graph.node(surface.get("layerSetID"))
    if layer_set is None:
        return None

    media_names: list[str] = []
    max_thickness = 0.0
    for layer_id in layer_set.get("layerIDs", []) or []:
        layer = graph.node(layer_id)
        if layer is None:
            continue
        media = graph.node(layer.get("mediaID"))
        if media and media.get("name"):
            media_names.append(str(media["name"]).lower())
        thickness = _coerce_float(graph.property_value(layer, "thickness"), default=0.0) or 0.0
        max_thickness = max(max_thickness, thickness)

    return _infer_material_from_media_names(media_names, layer_set.get("name"), max_thickness)


def _infer_material_from_media_names(
    media_names: list[str],
    layer_set_name: str | None,
    max_thickness: float,
) -> str | None:
    layer_set_name = (layer_set_name or "").lower()
    joined = " ".join(media_names + [layer_set_name])
    if not joined.strip():
        return None
    if "low-e" in joined or "low e" in joined:
        return "glass_low_e"
    if "glass" in joined:
        return "glass_standard"
    if "elevator" in joined and "shaft" in joined:
        return "elevator_shaft"
    if "metal" in joined or "steel" in joined:
        return "metal_fire_door"
    if "wood" in joined:
        return "wood_door"
    if "brick" in joined:
        return "brick"
    if "reinforced" in joined and "concrete" in joined:
        return "reinforced_concrete"
    if "concrete" in joined:
        return "concrete_block" if max_thickness < 0.25 else "reinforced_concrete"
    if "gypsum" in joined or "drywall" in joined:
        return "gypsum_double" if max_thickness >= 0.02 or media_names.count("gypsum") > 1 else "gypsum_single"
    return None


def _infer_opening_material(surface: dict[str, Any], room_type: RoomType) -> str:
    opening_kind = _opening_kind(surface)
    name = (surface.get("name") or "").lower()
    if opening_kind == "glazing":
        if "low-e" in name or "low e" in name:
            return "glass_low_e"
        return "glass_standard"
    if opening_kind == "garage_door":
        return "metal_fire_door"
    if room_type in {RoomType.MECHANICAL, RoomType.IT_SERVER, RoomType.STAIRWELL, RoomType.ELEVATOR}:
        return "metal_fire_door"
    return "wood_door"


def _infer_solid_wall_material(
    explicit_material_name: str | None,
    is_exterior: bool,
    room_types: list[RoomType],
) -> str:
    if explicit_material_name:
        return explicit_material_name
    if RoomType.ELEVATOR in room_types:
        return "elevator_shaft"
    if RoomType.STAIRWELL in room_types:
        return "reinforced_concrete"
    if RoomType.IT_SERVER in room_types or RoomType.MECHANICAL in room_types:
        return "concrete_block"
    if is_exterior:
        return "concrete_block"
    return "gypsum_double"


def _infer_room_type(zone_name: str, area_sqm: float) -> RoomType:
    name = zone_name.lower()
    if "elevator" in name or "lift" in name:
        return RoomType.ELEVATOR
    if "stair" in name:
        return RoomType.STAIRWELL
    if "conference" in name or "meeting" in name:
        return RoomType.CONFERENCE
    if "corridor" in name or "hall" in name:
        return RoomType.CORRIDOR
    if "lobby" in name or "reception" in name:
        return RoomType.LOBBY
    if "restroom" in name or "toilet" in name or "wc" in name or "bathroom" in name:
        return RoomType.RESTROOM
    if "break" in name or "kitchen" in name or "pantry" in name or "caf" in name:
        return RoomType.KITCHEN_BREAK
    if "server" in name or "it room" in name or "data room" in name:
        return RoomType.IT_SERVER
    if "mechanical" in name or "electrical" in name or "machine room" in name or "utility" in name:
        return RoomType.MECHANICAL
    if "storage" in name or "closet" in name:
        return RoomType.STORAGE
    if "loading dock" in name or name.startswith("dock") or " dock" in name:
        return RoomType.LOADING_DOCK
    if "warehouse" in name:
        return RoomType.WAREHOUSE_BAY
    if "office" in name:
        return RoomType.OPEN_OFFICE if area_sqm >= 40.0 else RoomType.PRIVATE_OFFICE
    if "lab" in name or "laboratory" in name or "chamber" in name or "testing" in name:
        return RoomType.OPEN_OFFICE
    return RoomType.OPEN_OFFICE


def _infer_building_type(rooms: list[Room]) -> BuildingType:
    warehouseish = sum(
        1 for room in rooms if room.room_type in {RoomType.WAREHOUSE_BAY, RoomType.LOADING_DOCK}
    )
    if warehouseish:
        return BuildingType.WAREHOUSE

    total_sqft = sum(room.area_sqft for room in rooms)
    if total_sqft >= 50_000:
        return BuildingType.LARGE_OFFICE
    return BuildingType.MEDIUM_OFFICE


def _window_side_for_segment(
    start: Point2D,
    end: Point2D,
    polygon: Polygon2D,
    relative_north_deg: float,
) -> str | None:
    signed_area = _signed_polygon_area(polygon.vertices)
    dx = end.x - start.x
    dy = end.y - start.y
    length = math.hypot(dx, dy)
    if length <= _EPS:
        return None

    tangent_x = dx / length
    tangent_y = dy / length
    if signed_area >= 0:
        outward_x = tangent_y
        outward_y = -tangent_x
    else:
        outward_x = -tangent_y
        outward_y = tangent_x

    return _vector_to_cardinal(outward_x, outward_y, relative_north_deg)


def _opening_covering_interval(
    openings: list[tuple[float, float, _OpeningInterval]],
    segment_start: float,
    segment_end: float,
) -> _OpeningInterval | None:
    midpoint = (segment_start + segment_end) / 2.0
    for opening_start, opening_end, opening in openings:
        if opening_start - _EPS <= midpoint <= opening_end + _EPS:
            return opening
    return None


def _opening_kind(surface: dict[str, Any]) -> str:
    surface_type = surface.get("surfaceType")
    if surface_type == "Door":
        return "door"
    if surface_type == "GarageDoor":
        return "garage_door"
    return "glazing"


def _to_canonical_interval(
    start_m: float,
    end_m: float,
    length_m: float,
    raw_is_canonical: bool,
) -> tuple[float, float]:
    if raw_is_canonical:
        return (start_m, end_m)
    return (length_m - end_m, length_m - start_m)


def _from_canonical_interval(
    start_m: float,
    end_m: float,
    length_m: float,
    raw_is_canonical: bool,
) -> tuple[float, float]:
    if raw_is_canonical:
        return (start_m, end_m)
    return (length_m - end_m, length_m - start_m)


def _point_key(point: Point2D) -> tuple[float, float]:
    return (round(point.x, 6), round(point.y, 6))


def _segment_key(start: Point2D, end: Point2D) -> tuple[tuple[float, float], tuple[float, float]]:
    start_key = _point_key(start)
    end_key = _point_key(end)
    return (start_key, end_key) if start_key <= end_key else (end_key, start_key)


def _point_along_edge(start: Point2D, end: Point2D, distance_m: float) -> Point2D:
    length = start.distance_to(end)
    if length <= _EPS:
        return start
    t = max(0.0, min(1.0, distance_m / length))
    return Point2D(
        start.x + (end.x - start.x) * t,
        start.y + (end.y - start.y) * t,
    )


def _material_thickness(material_name: str) -> float:
    return _DEFAULT_MATERIAL_THICKNESS_M.get(material_name, 0.05)


def _signed_polygon_area(points: list[Point2D]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        area += point.x * nxt.y - nxt.x * point.y
    return area / 2.0


def _vector_to_cardinal(dx: float, dy: float, relative_north_deg: float) -> str:
    # 0 degrees means north/+Y; positive angles rotate toward east/+X.
    angle_deg = (math.degrees(math.atan2(dx, dy)) - relative_north_deg) % 360.0
    if angle_deg < 45.0 or angle_deg >= 315.0:
        return "N"
    if angle_deg < 135.0:
        return "E"
    if angle_deg < 225.0:
        return "S"
    return "W"


def _coerce_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int | None = 0) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _convex_hull_polygon(points: list[Point2D]) -> Polygon2D:
    unique_points = sorted(
        {_point_key(point): point for point in points}.values(),
        key=lambda point: (point.x, point.y),
    )
    if len(unique_points) < 3:
        raise ValueError("Need at least three points to build a footprint")

    def cross(origin: Point2D, a: Point2D, b: Point2D) -> float:
        return (a.x - origin.x) * (b.y - origin.y) - (a.y - origin.y) * (b.x - origin.x)

    lower: list[Point2D] = []
    for point in unique_points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[Point2D] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    hull = lower[:-1] + upper[:-1]
    return Polygon2D(hull)
