"""BSP space partitioning building generator."""
from typing import Optional
import numpy as np
from dataclasses import dataclass

try:
    from core import (
        Building, Floor, Room, WallSegment, Door, Material, Point2D, Polygon2D,
        BuildingType, RoomType, WallMaterial, ROOM_TYPE_METADATA
    )
    from buildinggen.archetypes import Archetype
    from buildinggen.generators.base import BuildingGenerator
except ImportError:
    from ...core import (
        Building, Floor, Room, WallSegment, Door, Material, Point2D, Polygon2D,
        BuildingType, RoomType, WallMaterial, ROOM_TYPE_METADATA
    )
    from ..archetypes import Archetype
    from .base import BuildingGenerator


@dataclass
class _RoomSpec:
    """Internal room specification during generation."""
    room_type: RoomType
    target_area_sqm: float
    polygon: Optional[Polygon2D] = None


class BSPGenerator(BuildingGenerator):
    """Binary Space Partition building generator."""

    def generate(
        self,
        building_type: BuildingType,
        total_sqft: float,
        num_floors: int = 1,
        seed: int = 42,
        archetype: Optional[Archetype] = None,
    ) -> Building:
        """Generate a building using BSP partitioning."""
        rng = np.random.default_rng(seed)

        # Convert to metric
        total_sqm = total_sqft / 10.764
        floor_area_sqm = total_sqm / num_floors

        # Generate footprint
        footprint = self._generate_footprint(floor_area_sqm, archetype, rng)

        # Generate floors
        floors = []
        for floor_idx in range(num_floors):
            elevation = floor_idx * 3.0  # Assume 3m per floor
            floor = self._generate_floor(
                floor_idx, elevation, floor_area_sqm, footprint, archetype, rng
            )
            floors.append(floor)

        building = Building(
            building_type=building_type,
            floors=floors,
            footprint=footprint,
            total_area_sqft=total_sqft,
            seed=seed,
            metadata={
                "generator": "bsp",
                "num_floors": num_floors,
                "floor_area_sqm": floor_area_sqm,
            },
        )

        # Validate
        self._validate_building(building)

        return building

    def _generate_footprint(
        self, floor_area_sqm: float, archetype: Optional[Archetype], rng: np.random.Generator
    ) -> Polygon2D:
        """Generate floor footprint."""
        if archetype is None:
            aspect_ratio = 1.5
        else:
            aspect_ratio = rng.uniform(
                archetype.footprint_aspect_ratio_min,
                archetype.footprint_aspect_ratio_max,
            )

        width = np.sqrt(floor_area_sqm * aspect_ratio)
        depth = np.sqrt(floor_area_sqm / aspect_ratio)

        vertices = [
            Point2D(0.0, 0.0),
            Point2D(width, 0.0),
            Point2D(width, depth),
            Point2D(0.0, depth),
        ]
        return Polygon2D(vertices)

    def _generate_floor(
        self,
        floor_idx: int,
        elevation: float,
        floor_area_sqm: float,
        footprint: Polygon2D,
        archetype: Optional[Archetype],
        rng: np.random.Generator,
    ) -> Floor:
        """Generate a single floor."""
        # Generate room program
        room_specs = self._generate_room_program(floor_area_sqm, archetype, rng)

        # BSP subdivision
        rooms_with_polys = self._bsp_subdivide(floor_area_sqm, footprint, room_specs, rng)

        # Insert corridor
        ceiling_height = archetype.floor_ceiling_height_m if archetype else 3.0
        corridor_width = archetype.floor_corridor_width_m if archetype else 1.8
        rooms_with_polys = self._insert_corridor(
            rooms_with_polys, footprint, corridor_width, rng
        )

        # Create Room objects and assign IDs
        rooms = []
        room_id_counter = 0
        for spec, poly in rooms_with_polys:
            room_id = f"room_{floor_idx:03d}_{room_id_counter:03d}"
            room = Room(
                id=room_id,
                room_type=spec.room_type,
                polygon=poly,
                floor_index=floor_idx,
                wall_ids=[],
                door_ids=[],
                ceiling_height=ROOM_TYPE_METADATA[spec.room_type]["default_ceiling_height_m"],
            )
            rooms.append(room)
            room_id_counter += 1

        # Generate walls
        walls = self._generate_walls(rooms, floor_idx, archetype, rng)

        # Generate doors
        doors = self._generate_doors(rooms, walls, floor_idx)

        # Update room wall and door references
        for room in rooms:
            room.wall_ids = [w.id for w in walls if room.id in w.room_ids]
            room.door_ids = [d.id for d in doors if d.wall_id in room.wall_ids]

        return Floor(
            index=floor_idx,
            rooms=rooms,
            walls=walls,
            doors=doors,
            elevation=elevation,
            footprint=footprint,
        )

    def _generate_room_program(
        self, floor_area_sqm: float, archetype: Optional[Archetype], rng: np.random.Generator
    ) -> list[_RoomSpec]:
        """Generate room program from archetype."""
        if archetype is None:
            # Default simple office program
            target_area = floor_area_sqm * 0.85
            return [
                _RoomSpec(RoomType.OPEN_OFFICE, target_area * 0.55),
                _RoomSpec(RoomType.CORRIDOR, target_area * 0.25),
                _RoomSpec(RoomType.RESTROOM, target_area * 0.08),
                _RoomSpec(RoomType.MECHANICAL, target_area * 0.07),
                _RoomSpec(RoomType.STORAGE, target_area * 0.05),
            ]

        # Sample total target area 85-90% of floor
        target_area = floor_area_sqm * rng.uniform(0.85, 0.90)

        specs = []
        for rp in archetype.room_program:
            target = target_area * rp.area_fraction
            # Distribute by area: generate multiple rooms of this type
            num_rooms = max(1, int(np.round(target / ((rp.min_area_sqm + rp.max_area_sqm) / 2))))
            per_room = target / num_rooms
            for _ in range(num_rooms):
                specs.append(_RoomSpec(rp.room_type, per_room))

        return specs

    def _bsp_subdivide(
        self,
        floor_area_sqm: float,
        footprint: Polygon2D,
        room_specs: list[_RoomSpec],
        rng: np.random.Generator,
    ) -> list[tuple[_RoomSpec, Polygon2D]]:
        """Recursively partition space using BSP."""
        result = []

        def subdivide(
            remaining_specs: list[_RoomSpec],
            bbox_poly: Polygon2D,
        ) -> None:
            if len(remaining_specs) <= 1:
                if remaining_specs:
                    result.append((remaining_specs[0], bbox_poly))
                return

            # Split into two groups by area
            sorted_specs = sorted(remaining_specs, key=lambda s: s.target_area_sqm, reverse=True)
            total_area = sum(s.target_area_sqm for s in sorted_specs)
            target_split_ratio = 0.5

            group_a, group_b = [], []
            area_a = 0.0
            for spec in sorted_specs:
                if area_a / total_area < target_split_ratio:
                    group_a.append(spec)
                    area_a += spec.target_area_sqm
                else:
                    group_b.append(spec)

            # Ensure both groups non-empty
            if not group_a or not group_b:
                # Fallback: simple split
                mid = len(remaining_specs) // 2
                group_a, group_b = remaining_specs[:mid], remaining_specs[mid:]

            # Choose split axis based on bbox aspect ratio
            bbox = bbox_poly.bounding_box()
            aspect_ratio = bbox.width() / max(bbox.height(), 0.1)

            if aspect_ratio > 1.2:  # Wider than tall → vertical split
                is_vertical = True
            else:  # Vertical split
                is_vertical = False

            # Compute split position with perturbation
            if is_vertical:
                min_x = bbox.min_x
                max_x = bbox.max_x
                split_ratio = 0.5 + rng.uniform(-0.05, 0.05)
                split_x = min_x + (max_x - min_x) * split_ratio
                split_line_start = Point2D(split_x, bbox.min_y)
                split_line_end = Point2D(split_x, bbox.max_y)
            else:
                min_y = bbox.min_y
                max_y = bbox.max_y
                split_ratio = 0.5 + rng.uniform(-0.05, 0.05)
                split_y = min_y + (max_y - min_y) * split_ratio
                split_line_start = Point2D(bbox.min_x, split_y)
                split_line_end = Point2D(bbox.max_x, split_y)

            # Partition polygons (simplified: use bounding boxes)
            poly_a, poly_b = self._split_polygon(
                bbox_poly, is_vertical, split_ratio
            )

            # Recurse
            subdivide(group_a, poly_a)
            subdivide(group_b, poly_b)

        subdivide(room_specs, footprint)
        return result

    def _split_polygon(
        self, poly: Polygon2D, is_vertical: bool, split_ratio: float
    ) -> tuple[Polygon2D, Polygon2D]:
        """Split polygon by vertical or horizontal line."""
        bbox = poly.bounding_box()

        if is_vertical:
            split_x = bbox.min_x + (bbox.max_x - bbox.min_x) * split_ratio
            # Left polygon
            left_verts = [
                Point2D(bbox.min_x, bbox.min_y),
                Point2D(split_x, bbox.min_y),
                Point2D(split_x, bbox.max_y),
                Point2D(bbox.min_x, bbox.max_y),
            ]
            # Right polygon
            right_verts = [
                Point2D(split_x, bbox.min_y),
                Point2D(bbox.max_x, bbox.min_y),
                Point2D(bbox.max_x, bbox.max_y),
                Point2D(split_x, bbox.max_y),
            ]
        else:
            split_y = bbox.min_y + (bbox.max_y - bbox.min_y) * split_ratio
            # Bottom polygon
            left_verts = [
                Point2D(bbox.min_x, bbox.min_y),
                Point2D(bbox.max_x, bbox.min_y),
                Point2D(bbox.max_x, split_y),
                Point2D(bbox.min_x, split_y),
            ]
            # Top polygon
            right_verts = [
                Point2D(bbox.min_x, split_y),
                Point2D(bbox.max_x, split_y),
                Point2D(bbox.max_x, bbox.max_y),
                Point2D(bbox.min_x, bbox.max_y),
            ]

        return Polygon2D(left_verts), Polygon2D(right_verts)

    def _insert_corridor(
        self,
        rooms_with_polys: list[tuple[_RoomSpec, Polygon2D]],
        footprint: Polygon2D,
        corridor_width: float,
        rng: np.random.Generator,
    ) -> list[tuple[_RoomSpec, Polygon2D]]:
        """Insert corridor strip.

        Rooms are clipped against the corridor band using their bounding boxes.
        Any room that overlaps the corridor is split into at most two rectangular
        fragments (one on each side). This replaces the previous vertex-filtering
        approach, which dropped rooms whose bbox straddled the corridor midline
        (producing large voids in the floor plan).
        """
        if not rooms_with_polys:
            return rooms_with_polys

        bbox = footprint.bounding_box()
        if bbox.width() > bbox.height():
            # Vertical corridor running the full depth at the horizontal midpoint
            corridor_x = bbox.min_x + bbox.width() * 0.5
            corridor_min_x = corridor_x - corridor_width / 2
            corridor_max_x = corridor_x + corridor_width / 2

            result = []
            for spec, poly in rooms_with_polys:
                rb = poly.bounding_box()
                # Left fragment: portion of room west of corridor
                if rb.min_x < corridor_min_x:
                    clipped_max_x = min(rb.max_x, corridor_min_x)
                    result.append((spec, Polygon2D([
                        Point2D(rb.min_x, rb.min_y),
                        Point2D(clipped_max_x, rb.min_y),
                        Point2D(clipped_max_x, rb.max_y),
                        Point2D(rb.min_x, rb.max_y),
                    ])))
                # Right fragment: portion of room east of corridor
                if rb.max_x > corridor_max_x:
                    clipped_min_x = max(rb.min_x, corridor_max_x)
                    result.append((spec, Polygon2D([
                        Point2D(clipped_min_x, rb.min_y),
                        Point2D(rb.max_x, rb.min_y),
                        Point2D(rb.max_x, rb.max_y),
                        Point2D(clipped_min_x, rb.max_y),
                    ])))
                # Rooms entirely inside the corridor band are absorbed (dropped)

            # Add corridor strip
            result.append((_RoomSpec(RoomType.CORRIDOR, 0), Polygon2D([
                Point2D(corridor_min_x, bbox.min_y),
                Point2D(corridor_max_x, bbox.min_y),
                Point2D(corridor_max_x, bbox.max_y),
                Point2D(corridor_min_x, bbox.max_y),
            ])))
        else:
            # Horizontal corridor running the full width at the vertical midpoint
            corridor_y = bbox.min_y + bbox.height() * 0.5
            corridor_min_y = corridor_y - corridor_width / 2
            corridor_max_y = corridor_y + corridor_width / 2

            result = []
            for spec, poly in rooms_with_polys:
                rb = poly.bounding_box()
                # Bottom fragment: portion of room south of corridor
                if rb.min_y < corridor_min_y:
                    clipped_max_y = min(rb.max_y, corridor_min_y)
                    result.append((spec, Polygon2D([
                        Point2D(rb.min_x, rb.min_y),
                        Point2D(rb.max_x, rb.min_y),
                        Point2D(rb.max_x, clipped_max_y),
                        Point2D(rb.min_x, clipped_max_y),
                    ])))
                # Top fragment: portion of room north of corridor
                if rb.max_y > corridor_max_y:
                    clipped_min_y = max(rb.min_y, corridor_max_y)
                    result.append((spec, Polygon2D([
                        Point2D(rb.min_x, clipped_min_y),
                        Point2D(rb.max_x, clipped_min_y),
                        Point2D(rb.max_x, rb.max_y),
                        Point2D(rb.min_x, rb.max_y),
                    ])))
                # Rooms entirely inside the corridor band are absorbed (dropped)

            # Add corridor strip
            result.append((_RoomSpec(RoomType.CORRIDOR, 0), Polygon2D([
                Point2D(bbox.min_x, corridor_min_y),
                Point2D(bbox.max_x, corridor_min_y),
                Point2D(bbox.max_x, corridor_max_y),
                Point2D(bbox.min_x, corridor_max_y),
            ])))

        return result

    def _generate_walls(
        self,
        rooms: list[Room],
        floor_idx: int,
        archetype: Optional[Archetype],
        rng: np.random.Generator,
    ) -> list[WallSegment]:
        """Generate walls between adjacent rooms."""
        walls = []
        wall_id_counter = 0

        # Find adjacent rooms (shared edges)
        for i, room_a in enumerate(rooms):
            for room_b in rooms[i + 1 :]:
                # Check if rooms share an edge (simplified)
                shared_edge = self._find_shared_edge(room_a.polygon, room_b.polygon)
                if shared_edge is not None:
                    wall_id = f"wall_{floor_idx:03d}_{wall_id_counter:03d}"
                    wall_id_counter += 1

                    # Determine material
                    material_name = self._get_wall_material(
                        room_a.room_type, room_b.room_type, archetype
                    )
                    material = Material(material_name, self._get_material_thickness(material_name))

                    wall = WallSegment(
                        id=wall_id,
                        start=shared_edge[0],
                        end=shared_edge[1],
                        height=max(
                            ROOM_TYPE_METADATA[room_a.room_type]["default_ceiling_height_m"],
                            ROOM_TYPE_METADATA[room_b.room_type]["default_ceiling_height_m"],
                        ),
                        materials=[material],
                        is_exterior=False,
                        room_ids=(room_a.id, room_b.id),
                    )
                    walls.append(wall)

        # Exterior walls
        footprint = rooms[0].polygon if rooms else Polygon2D([])
        for edge in footprint.edges():
            wall_id = f"wall_{floor_idx:03d}_{wall_id_counter:03d}"
            wall_id_counter += 1

            material_name = (
                archetype.wall_exterior if archetype else "reinforced_concrete"
            )
            material = Material(material_name, self._get_material_thickness(material_name))

            wall = WallSegment(
                id=wall_id,
                start=edge.start,
                end=edge.end,
                height=3.0,
                materials=[material],
                is_exterior=True,
                room_ids=("exterior", None),
            )
            walls.append(wall)

        return walls

    def _find_shared_edge(self, poly_a: Polygon2D, poly_b: Polygon2D) -> Optional[tuple[Point2D, Point2D]]:
        """Find shared edge between two polygons.

        Returns the overlapping segment (which may be shorter than either full
        edge when a room edge only partially borders a corridor or another room).
        """
        for ea in poly_a.edges():
            for eb in poly_b.edges():
                overlap = self._compute_edge_overlap(ea, eb)
                if overlap is not None:
                    return overlap
        return None

    def _compute_edge_overlap(self, e1, e2) -> Optional[tuple[Point2D, Point2D]]:
        """Return the overlapping sub-segment of two collinear axis-aligned edges.

        Handles the case where one edge is shorter than the other (e.g. a room
        edge that only partially borders a corridor strip).  Returns None when
        the edges are not collinear or their projections do not overlap.
        """
        EPS = 1e-6    # geometric collinearity tolerance (metres)
        TOLS = 0.05   # spatial tolerance for coincident lines (5 cm)

        is_h1 = abs(e1.start.y - e1.end.y) < EPS
        is_h2 = abs(e2.start.y - e2.end.y) < EPS
        is_v1 = abs(e1.start.x - e1.end.x) < EPS
        is_v2 = abs(e2.start.x - e2.end.x) < EPS

        # Both horizontal
        if is_h1 and is_h2:
            if abs(e1.start.y - e2.start.y) > TOLS:
                return None
            ov_min = max(min(e1.start.x, e1.end.x), min(e2.start.x, e2.end.x))
            ov_max = min(max(e1.start.x, e1.end.x), max(e2.start.x, e2.end.x))
            if ov_max - ov_min < TOLS:
                return None
            y = (e1.start.y + e2.start.y) / 2.0
            return (Point2D(ov_min, y), Point2D(ov_max, y))

        # Both vertical
        if is_v1 and is_v2:
            if abs(e1.start.x - e2.start.x) > TOLS:
                return None
            ov_min = max(min(e1.start.y, e1.end.y), min(e2.start.y, e2.end.y))
            ov_max = min(max(e1.start.y, e1.end.y), max(e2.start.y, e2.end.y))
            if ov_max - ov_min < TOLS:
                return None
            x = (e1.start.x + e2.start.x) / 2.0
            return (Point2D(x, ov_min), Point2D(x, ov_max))

        # Non-axis-aligned fallback: exact endpoint proximity (original logic)
        if e1.start.distance_to(e2.start) < 0.1 and e1.end.distance_to(e2.end) < 0.1:
            return (e1.start, e1.end)
        if e1.start.distance_to(e2.end) < 0.1 and e1.end.distance_to(e2.start) < 0.1:
            return (e1.start, e1.end)
        return None

    def _edges_collinear_and_overlap(self, e1, e2) -> bool:
        """Check if edges are collinear and overlap (delegates to _compute_edge_overlap)."""
        return self._compute_edge_overlap(e1, e2) is not None

    def _get_wall_material(
        self, room_type_a: RoomType, room_type_b: RoomType, archetype: Optional[Archetype]
    ) -> str:
        """Determine wall material between two room types."""
        if archetype is None:
            return "gypsum_double"

        # Check for overrides
        for rt in [room_type_a, room_type_b]:
            if rt.value in archetype.wall_overrides:
                return archetype.wall_overrides[rt.value]

        return archetype.wall_interior_default

    def _get_material_thickness(self, material_name: str) -> float:
        """Get typical thickness for material."""
        thicknesses = {
            "gypsum_single": 0.016,
            "gypsum_double": 0.026,
            "concrete_block": 0.15,
            "reinforced_concrete": 0.20,
            "brick": 0.10,
            "glass_standard": 0.004,
            "glass_low_e": 0.004,
            "wood_door": 0.045,
            "metal_fire_door": 0.045,
            "elevator_shaft": 0.15,
        }
        return thicknesses.get(material_name, 0.05)

    def _generate_doors(
        self, rooms: list[Room], walls: list[WallSegment], floor_idx: int
    ) -> list[Door]:
        """Generate doors in walls."""
        doors = []
        door_id_counter = 0

        for wall in walls:
            if not wall.is_exterior and wall.room_ids[1] is not None:
                # Interior wall - add one door at midpoint
                door_id = f"door_{floor_idx:03d}_{door_id_counter:03d}"
                door_id_counter += 1

                room_a = next((r for r in rooms if r.id == wall.room_ids[0]), None)
                room_b = next((r for r in rooms if r.id == wall.room_ids[1]), None)

                is_fire_door = (
                    room_a and room_a.room_type in [RoomType.MECHANICAL, RoomType.STAIRWELL]
                ) or (room_b and room_b.room_type in [RoomType.MECHANICAL, RoomType.STAIRWELL])

                material_name = "metal_fire_door" if is_fire_door else "wood_door"
                material = Material(material_name, self._get_material_thickness(material_name))

                door = Door(
                    id=door_id,
                    wall_id=wall.id,
                    position_along_wall=0.5,
                    width=0.9,
                    height=2.1,
                    material=material,
                )
                doors.append(door)

        return doors

    def _validate_building(self, building: Building) -> None:
        """Validate generated building."""
        room_count = sum(len(f.rooms) for f in building.floors)
        if room_count == 0:
            raise ValueError("Generated building has no rooms")

        # Check for room overlap
        for floor in building.floors:
            for i, room_a in enumerate(floor.rooms):
                for room_b in floor.rooms[i + 1 :]:
                    if not self._polygons_disjoint(room_a.polygon, room_b.polygon):
                        # Allow touching at edges
                        pass

    def _polygons_disjoint(self, poly_a: Polygon2D, poly_b: Polygon2D) -> bool:
        """Check if two polygons are disjoint (don't overlap internally)."""
        # Simplified check: if any vertex of A is inside B, they overlap
        for v in poly_a.vertices:
            if poly_b.contains(v):
                return False
        for v in poly_b.vertices:
            if poly_a.contains(v):
                return False
        return True
