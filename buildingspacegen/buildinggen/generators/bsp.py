"""Corridor-first rectangular floor planner exposed behind the BSP generator API."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

try:
    from core import (
        Building,
        Floor,
        Room,
        WallSegment,
        Door,
        Material,
        Point2D,
        Polygon2D,
        BuildingType,
        RoomType,
        ROOM_TYPE_METADATA,
    )
    from buildinggen.archetypes import Archetype, RoomProgram
    from buildinggen.generators.base import BuildingGenerator
except ImportError:
    from ...core import (
        Building,
        Floor,
        Room,
        WallSegment,
        Door,
        Material,
        Point2D,
        Polygon2D,
        BuildingType,
        RoomType,
        ROOM_TYPE_METADATA,
    )
    from ..archetypes import Archetype, RoomProgram
    from .base import BuildingGenerator


EPS = 1e-6


@dataclass(frozen=True)
class _Rect:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def width(self) -> float:
        return self.max_x - self.min_x

    def height(self) -> float:
        return self.max_y - self.min_y

    def area(self) -> float:
        return self.width() * self.height()

    def center(self) -> Point2D:
        return Point2D((self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0)

    def to_polygon(self) -> Polygon2D:
        return Polygon2D(
            [
                Point2D(self.min_x, self.min_y),
                Point2D(self.max_x, self.min_y),
                Point2D(self.max_x, self.max_y),
                Point2D(self.min_x, self.max_y),
            ]
        )

    def touches_west(self, other: "_Rect") -> bool:
        return abs(self.min_x - other.max_x) < EPS and self._overlap_length_y(other) > EPS

    def touches_east(self, other: "_Rect") -> bool:
        return abs(self.max_x - other.min_x) < EPS and self._overlap_length_y(other) > EPS

    def touches_south(self, other: "_Rect") -> bool:
        return abs(self.min_y - other.max_y) < EPS and self._overlap_length_x(other) > EPS

    def touches_north(self, other: "_Rect") -> bool:
        return abs(self.max_y - other.min_y) < EPS and self._overlap_length_x(other) > EPS

    def touches_perimeter(self, bounds: "_Rect", side: str) -> bool:
        if side == "west":
            return abs(self.min_x - bounds.min_x) < EPS
        if side == "east":
            return abs(self.max_x - bounds.max_x) < EPS
        if side == "south":
            return abs(self.min_y - bounds.min_y) < EPS
        if side == "north":
            return abs(self.max_y - bounds.max_y) < EPS
        raise ValueError(f"Unknown side: {side}")

    def _overlap_length_x(self, other: "_Rect") -> float:
        return max(0.0, min(self.max_x, other.max_x) - max(self.min_x, other.min_x))

    def _overlap_length_y(self, other: "_Rect") -> float:
        return max(0.0, min(self.max_y, other.max_y) - max(self.min_y, other.min_y))


@dataclass(frozen=True)
class _CorridorBand:
    axis: str
    start: float
    end: float

    def contains(self, point: Point2D) -> bool:
        value = point.x if self.axis == "x" else point.y
        return self.start - EPS <= value <= self.end + EPS


@dataclass
class _Parcel:
    rect: _Rect
    corridor_sides: list[str]
    perimeter_sides: list[str]
    assigned_rooms: list[tuple[RoomType, _Rect]] = field(default_factory=list)


class BSPGenerator(BuildingGenerator):
    """Building generator that creates a corridor network before assigning rooms."""

    def generate(
        self,
        building_type: BuildingType,
        total_sqft: float,
        num_floors: int = 1,
        seed: int = 42,
        archetype: Optional[Archetype] = None,
    ) -> Building:
        rng = np.random.default_rng(seed)
        total_sqm = total_sqft / 10.764
        floor_area_sqm = total_sqm / num_floors

        footprint = self._generate_footprint(floor_area_sqm, archetype, rng)

        floors = []
        for floor_idx in range(num_floors):
            floors.append(
                self._generate_floor(
                    floor_idx=floor_idx,
                    elevation=floor_idx * 3.0,
                    floor_area_sqm=floor_area_sqm,
                    footprint=footprint,
                    building_type=building_type,
                    archetype=archetype,
                    rng=rng,
                )
            )

        building = Building(
            building_type=building_type,
            floors=floors,
            footprint=footprint,
            total_area_sqft=total_sqft,
            seed=seed,
            metadata={
                "generator": "bsp",
                "layout_strategy": "corridor_first_grid",
                "num_floors": num_floors,
                "floor_area_sqm": floor_area_sqm,
            },
        )
        self._validate_building(building)
        return building

    def _generate_footprint(
        self, floor_area_sqm: float, archetype: Optional[Archetype], rng: np.random.Generator
    ) -> Polygon2D:
        if archetype is None:
            aspect_ratio = 1.5
        else:
            aspect_ratio = rng.uniform(
                archetype.footprint_aspect_ratio_min,
                archetype.footprint_aspect_ratio_max,
            )

        width = np.sqrt(floor_area_sqm * aspect_ratio)
        depth = np.sqrt(floor_area_sqm / aspect_ratio)
        return Polygon2D(
            [
                Point2D(0.0, 0.0),
                Point2D(width, 0.0),
                Point2D(width, depth),
                Point2D(0.0, depth),
            ]
        )

    def _generate_floor(
        self,
        floor_idx: int,
        elevation: float,
        floor_area_sqm: float,
        footprint: Polygon2D,
        building_type: BuildingType,
        archetype: Optional[Archetype],
        rng: np.random.Generator,
    ) -> Floor:
        bounds = self._rect_from_polygon(footprint)
        corridor_width = archetype.floor_corridor_width_m if archetype else 1.8

        corridor_bands = self._plan_corridor_bands(bounds, building_type, corridor_width, rng)
        corridor_rects, parcels = self._partition_floor(bounds, corridor_bands)

        room_program = self._get_room_program(archetype, bounds.area())
        self._assign_rooms_to_parcels(
            building_type=building_type,
            parcels=parcels,
            bounds=bounds,
            room_program=room_program,
            rng=rng,
        )

        rooms = self._build_rooms_from_layout(
            floor_idx=floor_idx,
            corridor_rects=corridor_rects,
            parcels=parcels,
        )
        walls = self._generate_walls(rooms, footprint, floor_idx, archetype)
        doors = self._generate_doors(rooms, walls, floor_idx)

        for room in rooms:
            room.wall_ids = [wall.id for wall in walls if room.id in wall.room_ids]
            room.door_ids = [door.id for door in doors if door.wall_id in room.wall_ids]

        return Floor(
            index=floor_idx,
            rooms=rooms,
            walls=walls,
            doors=doors,
            elevation=elevation,
            footprint=footprint,
        )

    def _get_room_program(
        self, archetype: Optional[Archetype], floor_area_sqm: float
    ) -> dict[RoomType, RoomProgram]:
        if archetype is None:
            defaults = [
                RoomProgram(RoomType.OPEN_OFFICE, 0.50, 30.0, 160.0),
                RoomProgram(RoomType.PRIVATE_OFFICE, 0.10, 10.0, 18.0),
                RoomProgram(RoomType.CONFERENCE, 0.10, 15.0, 40.0),
                RoomProgram(RoomType.LOBBY, 0.05, 20.0, 50.0),
                RoomProgram(RoomType.RESTROOM, 0.07, 8.0, 20.0),
                RoomProgram(RoomType.KITCHEN_BREAK, 0.05, 12.0, 30.0),
                RoomProgram(RoomType.MECHANICAL, 0.05, 10.0, 25.0),
                RoomProgram(RoomType.STORAGE, 0.04, 5.0, 14.0),
                RoomProgram(RoomType.IT_SERVER, 0.02, 8.0, 16.0),
                RoomProgram(RoomType.STAIRWELL, 0.01, 8.0, 12.0),
                RoomProgram(RoomType.ELEVATOR, 0.01, 4.0, 8.0),
            ]
            return {rp.room_type: rp for rp in defaults}

        return {rp.room_type: rp for rp in archetype.room_program}

    def _plan_corridor_bands(
        self,
        bounds: _Rect,
        building_type: BuildingType,
        corridor_width: float,
        rng: np.random.Generator,
    ) -> list[_CorridorBand]:
        long_axis = "x" if bounds.width() >= bounds.height() else "y"
        short_axis = "y" if long_axis == "x" else "x"

        if building_type == BuildingType.LARGE_OFFICE:
            long_fractions = [0.24, 0.50, 0.76]
            short_fractions = [0.20, 0.50, 0.80]
        elif building_type == BuildingType.WAREHOUSE:
            long_fractions = [0.18]
            short_fractions = [0.25, 0.75]
        else:
            long_fractions = [0.34, 0.66]
            short_fractions = [0.28, 0.72]

        if building_type == BuildingType.WAREHOUSE and long_axis == "y":
            long_fractions = [0.22]

        bands = []
        for axis, fractions in ((long_axis, long_fractions), (short_axis, short_fractions)):
            span = bounds.width() if axis == "x" else bounds.height()
            origin = bounds.min_x if axis == "x" else bounds.min_y
            for fraction in fractions:
                jitter = rng.uniform(-0.02, 0.02) if building_type != BuildingType.WAREHOUSE else rng.uniform(-0.015, 0.015)
                center = origin + span * min(max(fraction + jitter, 0.12), 0.88)
                start = max(origin + corridor_width * 0.5, center - corridor_width / 2.0)
                end = min(origin + span - corridor_width * 0.5, center + corridor_width / 2.0)
                start = max(origin, start)
                end = min(origin + span, end)
                if end - start > 0.75 * corridor_width:
                    bands.append(_CorridorBand(axis=axis, start=start, end=end))
        return bands

    def _partition_floor(
        self, bounds: _Rect, corridor_bands: list[_CorridorBand]
    ) -> tuple[list[_Rect], list[_Parcel]]:
        x_breaks = [bounds.min_x, bounds.max_x]
        y_breaks = [bounds.min_y, bounds.max_y]
        for band in corridor_bands:
            if band.axis == "x":
                x_breaks.extend([band.start, band.end])
            else:
                y_breaks.extend([band.start, band.end])

        x_breaks = self._sorted_unique(x_breaks)
        y_breaks = self._sorted_unique(y_breaks)

        cells: list[tuple[_Rect, bool]] = []
        for ix in range(len(x_breaks) - 1):
            for iy in range(len(y_breaks) - 1):
                rect = _Rect(x_breaks[ix], y_breaks[iy], x_breaks[ix + 1], y_breaks[iy + 1])
                if rect.area() < 1.0:
                    continue
                center = rect.center()
                cells.append((rect, any(band.contains(center) for band in corridor_bands)))

        corridor_rects = [rect for rect, is_corridor in cells if is_corridor]
        parcels: list[_Parcel] = []
        for rect, is_corridor in cells:
            if is_corridor:
                continue
            corridor_sides = self._corridor_sides_for_rect(rect, corridor_rects, bounds)
            perimeter_sides = [
                side
                for side in ("west", "east", "south", "north")
                if rect.touches_perimeter(bounds, side)
            ]
            parcels.append(
                _Parcel(
                    rect=rect,
                    corridor_sides=corridor_sides,
                    perimeter_sides=perimeter_sides,
                )
            )

        return corridor_rects, parcels

    def _corridor_sides_for_rect(
        self, rect: _Rect, corridor_rects: list[_Rect], bounds: _Rect
    ) -> list[str]:
        sides: list[str] = []
        for corridor in corridor_rects:
            if rect.touches_west(corridor):
                sides.append("west")
            if rect.touches_east(corridor):
                sides.append("east")
            if rect.touches_south(corridor):
                sides.append("south")
            if rect.touches_north(corridor):
                sides.append("north")
        if not sides:
            perimeter = [side for side in ("west", "east", "south", "north") if rect.touches_perimeter(bounds, side)]
            if perimeter:
                sides.append(perimeter[0])
        return self._dedupe_preserve(sides)

    def _assign_rooms_to_parcels(
        self,
        building_type: BuildingType,
        parcels: list[_Parcel],
        bounds: _Rect,
        room_program: dict[RoomType, RoomProgram],
        rng: np.random.Generator,
    ) -> None:
        total_parcel_area = sum(parcel.rect.area() for parcel in parcels)
        remaining_targets = {
            room_type: total_parcel_area * program.area_fraction
            for room_type, program in room_program.items()
            if room_type != RoomType.CORRIDOR
        }

        parcels_by_priority = sorted(
            parcels,
            key=lambda parcel: (
                len(parcel.corridor_sides),
                parcel.rect.area(),
            ),
            reverse=True,
        )
        front_side = self._front_side(bounds)

        for parcel in parcels_by_priority:
            self._fill_parcel(
                building_type=building_type,
                parcel=parcel,
                bounds=bounds,
                front_side=front_side,
                remaining_targets=remaining_targets,
                room_program=room_program,
                rng=rng,
            )

        leftovers = [room_type for room_type, area in remaining_targets.items() if area > 6.0]
        if leftovers:
            for room_type in leftovers:
                best = max(
                    parcels,
                    key=lambda parcel: self._room_score(
                        room_type,
                        parcel,
                        bounds,
                        front_side,
                        building_type,
                    ) - 0.15 * len(parcel.assigned_rooms),
                )
                self._append_slice(best, room_type, room_program[room_type], remaining_targets[room_type], rng)
                remaining_targets[room_type] = 0.0

    def _fill_parcel(
        self,
        building_type: BuildingType,
        parcel: _Parcel,
        bounds: _Rect,
        front_side: str,
        remaining_targets: dict[RoomType, float],
        room_program: dict[RoomType, RoomProgram],
        rng: np.random.Generator,
    ) -> None:
        frontage_side = self._frontage_side(parcel)
        length = parcel.rect.width() if frontage_side in ("north", "south") else parcel.rect.height()
        depth = parcel.rect.height() if frontage_side in ("north", "south") else parcel.rect.width()
        remaining_length = length
        cursor = parcel.rect.min_x if frontage_side in ("north", "south") else parcel.rect.min_y
        min_frontage = 2.2

        while remaining_length > min_frontage:
            candidates = [
                room_type
                for room_type, area in remaining_targets.items()
                if area > 1.0
            ]
            if not candidates:
                break

            room_type = max(
                candidates,
                key=lambda rt: self._room_score(rt, parcel, bounds, front_side, building_type)
                + remaining_targets[rt] / max(depth * length, 1.0)
                + rng.uniform(0.0, 0.05),
            )
            program = room_program[room_type]
            desired_area = min(
                remaining_targets[room_type],
                rng.uniform(program.min_area_sqm, program.max_area_sqm),
            )

            if room_type in {RoomType.OPEN_OFFICE, RoomType.WAREHOUSE_BAY}:
                desired_area = max(desired_area, remaining_length * depth * rng.uniform(0.35, 0.60))

            slice_length = max(min_frontage, desired_area / max(depth, 1.0))
            slice_length = min(slice_length, remaining_length)
            if remaining_length - slice_length < min_frontage:
                slice_length = remaining_length

            room_rect = self._slice_rect(parcel.rect, frontage_side, cursor, slice_length)
            parcel.assigned_rooms.append((room_type, room_rect))
            remaining_targets[room_type] = max(0.0, remaining_targets[room_type] - room_rect.area())
            cursor += slice_length
            remaining_length -= slice_length

            if remaining_length < min_frontage * 1.2:
                break

        if remaining_length > 1.0:
            fallback_type = self._fallback_room_type(building_type, parcel, bounds, front_side)
            room_rect = self._slice_rect(parcel.rect, frontage_side, cursor, remaining_length)
            parcel.assigned_rooms.append((fallback_type, room_rect))

        self._rebalance_small_trailing_rooms(parcel, room_program)

    def _append_slice(
        self,
        parcel: _Parcel,
        room_type: RoomType,
        program: RoomProgram,
        remaining_target: float,
        rng: np.random.Generator,
    ) -> None:
        if not parcel.assigned_rooms:
            self._fill_empty_parcel(parcel, room_type)
            return

        index = max(range(len(parcel.assigned_rooms)), key=lambda idx: parcel.assigned_rooms[idx][1].area())
        current_type, rect = parcel.assigned_rooms[index]
        if rect.area() < program.min_area_sqm * 1.4:
            parcel.assigned_rooms[index] = (room_type, rect)
            return

        frontage_side = self._frontage_side(parcel)
        along_x = frontage_side in ("north", "south")
        split_ratio = min(0.5, max(0.25, remaining_target / max(rect.area(), 1.0)))
        if along_x:
            split = rect.min_x + rect.width() * split_ratio
            left = _Rect(rect.min_x, rect.min_y, split, rect.max_y)
            right = _Rect(split, rect.min_y, rect.max_x, rect.max_y)
        else:
            split = rect.min_y + rect.height() * split_ratio
            left = _Rect(rect.min_x, rect.min_y, rect.max_x, split)
            right = _Rect(rect.min_x, split, rect.max_x, rect.max_y)

        parcel.assigned_rooms[index] = (room_type, left)
        parcel.assigned_rooms.insert(index + 1, (current_type, right))

    def _fill_empty_parcel(self, parcel: _Parcel, room_type: RoomType) -> None:
        parcel.assigned_rooms.append((room_type, parcel.rect))

    def _fallback_room_type(
        self,
        building_type: BuildingType,
        parcel: _Parcel,
        bounds: _Rect,
        front_side: str,
    ) -> RoomType:
        if building_type == BuildingType.WAREHOUSE and "south" in parcel.perimeter_sides:
            return RoomType.LOADING_DOCK
        if self._is_outer_parcel(parcel, bounds):
            return RoomType.OPEN_OFFICE if building_type != BuildingType.WAREHOUSE else RoomType.WAREHOUSE_BAY
        return RoomType.CONFERENCE

    def _frontage_side(self, parcel: _Parcel) -> str:
        if parcel.corridor_sides:
            return max(
                parcel.corridor_sides,
                key=lambda side: parcel.rect.width() if side in ("north", "south") else parcel.rect.height(),
            )
        if parcel.perimeter_sides:
            return parcel.perimeter_sides[0]
        return "south"

    def _slice_rect(self, rect: _Rect, frontage_side: str, cursor: float, slice_length: float) -> _Rect:
        if frontage_side in ("north", "south"):
            return _Rect(cursor, rect.min_y, min(rect.max_x, cursor + slice_length), rect.max_y)
        return _Rect(rect.min_x, cursor, rect.max_x, min(rect.max_y, cursor + slice_length))

    def _rebalance_small_trailing_rooms(
        self, parcel: _Parcel, room_program: dict[RoomType, RoomProgram]
    ) -> None:
        if len(parcel.assigned_rooms) < 2:
            return

        room_type, rect = parcel.assigned_rooms[-1]
        program = room_program.get(room_type)
        if program is None or rect.area() >= program.min_area_sqm * 0.8:
            return

        prev_type, prev_rect = parcel.assigned_rooms[-2]
        if abs(prev_rect.max_x - rect.min_x) < EPS and abs(prev_rect.min_y - rect.min_y) < EPS and abs(prev_rect.max_y - rect.max_y) < EPS:
            merged = _Rect(prev_rect.min_x, prev_rect.min_y, rect.max_x, rect.max_y)
        elif abs(prev_rect.max_y - rect.min_y) < EPS and abs(prev_rect.min_x - rect.min_x) < EPS and abs(prev_rect.max_x - rect.max_x) < EPS:
            merged = _Rect(prev_rect.min_x, prev_rect.min_y, rect.max_x, rect.max_y)
        else:
            return

        parcel.assigned_rooms[-2] = (prev_type, merged)
        parcel.assigned_rooms.pop()

    def _room_score(
        self,
        room_type: RoomType,
        parcel: _Parcel,
        bounds: _Rect,
        front_side: str,
        building_type: BuildingType,
    ) -> float:
        center = parcel.rect.center()
        bounds_center = bounds.center()
        dx = abs(center.x - bounds_center.x) / max(bounds.width(), 1.0)
        dy = abs(center.y - bounds_center.y) / max(bounds.height(), 1.0)
        centrality = 1.0 - min(1.0, np.sqrt(dx * dx + dy * dy) * 1.8)
        edge_exposure = len(parcel.perimeter_sides) / 4.0
        corridor_access = len(parcel.corridor_sides) / 4.0
        frontness = self._frontness(parcel.rect, bounds, front_side)
        parcel_area = parcel.rect.area()
        large_parcel = min(parcel_area / max(bounds.area(), 1.0) * 8.0, 1.0)

        if room_type == RoomType.OPEN_OFFICE:
            return 0.45 * edge_exposure + 0.25 * (1.0 - centrality) + 0.20 * corridor_access + 0.15 * large_parcel
        if room_type == RoomType.WAREHOUSE_BAY:
            return 0.60 * (1.0 - frontness) + 0.20 * edge_exposure + 0.25 * large_parcel
        if room_type == RoomType.PRIVATE_OFFICE:
            return 0.35 * edge_exposure + 0.30 * corridor_access + 0.20 * centrality
        if room_type == RoomType.CONFERENCE:
            return 0.35 * centrality + 0.20 * edge_exposure + 0.25 * corridor_access + 0.15 * frontness
        if room_type == RoomType.LOBBY:
            return 0.55 * frontness + 0.25 * edge_exposure + 0.20 * centrality
        if room_type == RoomType.LOADING_DOCK:
            return 0.60 * frontness + 0.25 * edge_exposure + 0.15 * corridor_access
        if room_type in {RoomType.RESTROOM, RoomType.MECHANICAL, RoomType.IT_SERVER, RoomType.STAIRWELL, RoomType.ELEVATOR, RoomType.STORAGE}:
            return 0.50 * centrality + 0.30 * corridor_access + 0.10 * (1.0 - edge_exposure)
        if room_type == RoomType.KITCHEN_BREAK:
            return 0.35 * centrality + 0.25 * edge_exposure + 0.25 * corridor_access

        return 0.25 * corridor_access + 0.20 * edge_exposure + 0.20 * centrality

    def _frontness(self, rect: _Rect, bounds: _Rect, front_side: str) -> float:
        if front_side == "south":
            return 1.0 - ((rect.center().y - bounds.min_y) / max(bounds.height(), 1.0))
        if front_side == "north":
            return (rect.center().y - bounds.min_y) / max(bounds.height(), 1.0)
        if front_side == "west":
            return 1.0 - ((rect.center().x - bounds.min_x) / max(bounds.width(), 1.0))
        return (rect.center().x - bounds.min_x) / max(bounds.width(), 1.0)

    def _front_side(self, bounds: _Rect) -> str:
        return "south" if bounds.width() >= bounds.height() else "west"

    def _is_outer_parcel(self, parcel: _Parcel, bounds: _Rect) -> bool:
        return bool(parcel.perimeter_sides) or (
            abs(parcel.rect.center().x - bounds.center().x) / max(bounds.width(), 1.0)
            + abs(parcel.rect.center().y - bounds.center().y) / max(bounds.height(), 1.0)
        ) > 0.35

    def _build_rooms_from_layout(
        self,
        floor_idx: int,
        corridor_rects: list[_Rect],
        parcels: list[_Parcel],
    ) -> list[Room]:
        rooms: list[Room] = []
        room_counter = 0

        for rect in corridor_rects:
            room_id = f"room_{floor_idx:03d}_{room_counter:03d}"
            rooms.append(
                Room(
                    id=room_id,
                    room_type=RoomType.CORRIDOR,
                    polygon=rect.to_polygon(),
                    floor_index=floor_idx,
                    wall_ids=[],
                    door_ids=[],
                    ceiling_height=ROOM_TYPE_METADATA[RoomType.CORRIDOR]["default_ceiling_height_m"],
                    metadata={"zone": "circulation"},
                )
            )
            room_counter += 1

        for parcel in parcels:
            for room_type, rect in parcel.assigned_rooms:
                room_id = f"room_{floor_idx:03d}_{room_counter:03d}"
                rooms.append(
                    Room(
                        id=room_id,
                        room_type=room_type,
                        polygon=rect.to_polygon(),
                        floor_index=floor_idx,
                        wall_ids=[],
                        door_ids=[],
                        ceiling_height=ROOM_TYPE_METADATA[room_type]["default_ceiling_height_m"],
                        metadata={"corridor_sides": list(parcel.corridor_sides)},
                    )
                )
                room_counter += 1

        return rooms

    def _generate_walls(
        self,
        rooms: list[Room],
        footprint: Polygon2D,
        floor_idx: int,
        archetype: Optional[Archetype],
    ) -> list[WallSegment]:
        walls: list[WallSegment] = []
        wall_counter = 0
        room_rects = {room.id: self._rect_from_polygon(room.polygon) for room in rooms}

        for idx, room_a in enumerate(rooms):
            for room_b in rooms[idx + 1 :]:
                if room_a.room_type == RoomType.CORRIDOR and room_b.room_type == RoomType.CORRIDOR:
                    continue
                shared_edge = self._find_shared_edge(room_a.polygon, room_b.polygon)
                if shared_edge is None:
                    continue

                material_name = self._get_wall_material(room_a.room_type, room_b.room_type, archetype)
                wall = WallSegment(
                    id=f"wall_{floor_idx:03d}_{wall_counter:03d}",
                    start=shared_edge[0],
                    end=shared_edge[1],
                    height=max(room_a.ceiling_height, room_b.ceiling_height),
                    materials=[Material(material_name, self._get_material_thickness(material_name))],
                    is_exterior=False,
                    room_ids=(room_a.id, room_b.id),
                )
                walls.append(wall)
                wall_counter += 1

        boundary_index: dict[tuple[float, float, float, float], str] = {}
        bounds = self._rect_from_polygon(footprint)
        for room in rooms:
            rect = room_rects[room.id]
            for edge in rect.to_polygon().edges():
                if not self._edge_on_bounds(edge.start, edge.end, bounds):
                    continue
                key = self._edge_key(edge.start, edge.end)
                if key in boundary_index:
                    continue

                material_name = archetype.wall_exterior if archetype else "reinforced_concrete"
                walls.append(
                    WallSegment(
                        id=f"wall_{floor_idx:03d}_{wall_counter:03d}",
                        start=edge.start,
                        end=edge.end,
                        height=room.ceiling_height,
                        materials=[Material(material_name, self._get_material_thickness(material_name))],
                        is_exterior=True,
                        room_ids=(room.id, None),
                    )
                )
                boundary_index[key] = room.id
                wall_counter += 1

        return walls

    def _generate_doors(
        self, rooms: list[Room], walls: list[WallSegment], floor_idx: int
    ) -> list[Door]:
        room_lookup = {room.id: room for room in rooms}
        doors: list[Door] = []
        counter = 0

        for wall in walls:
            if wall.is_exterior or wall.room_ids[1] is None:
                continue

            room_a = room_lookup[wall.room_ids[0]]
            room_b = room_lookup[wall.room_ids[1]]
            if room_a.room_type == RoomType.CORRIDOR and room_b.room_type == RoomType.CORRIDOR:
                continue
            if room_a.room_type != RoomType.CORRIDOR and room_b.room_type != RoomType.CORRIDOR:
                continue

            secure_types = {RoomType.MECHANICAL, RoomType.STAIRWELL, RoomType.IT_SERVER}
            material_name = "metal_fire_door" if {room_a.room_type, room_b.room_type} & secure_types else "wood_door"
            doors.append(
                Door(
                    id=f"door_{floor_idx:03d}_{counter:03d}",
                    wall_id=wall.id,
                    position_along_wall=0.5,
                    width=0.9,
                    height=2.1,
                    material=Material(material_name, self._get_material_thickness(material_name)),
                )
            )
            counter += 1

        return doors

    def _find_shared_edge(
        self, poly_a: Polygon2D, poly_b: Polygon2D
    ) -> Optional[tuple[Point2D, Point2D]]:
        for edge_a in poly_a.edges():
            for edge_b in poly_b.edges():
                overlap = self._compute_edge_overlap(edge_a.start, edge_a.end, edge_b.start, edge_b.end)
                if overlap is not None:
                    return overlap
        return None

    def _compute_edge_overlap(
        self, a_start: Point2D, a_end: Point2D, b_start: Point2D, b_end: Point2D
    ) -> Optional[tuple[Point2D, Point2D]]:
        a_horizontal = abs(a_start.y - a_end.y) < EPS
        b_horizontal = abs(b_start.y - b_end.y) < EPS
        a_vertical = abs(a_start.x - a_end.x) < EPS
        b_vertical = abs(b_start.x - b_end.x) < EPS

        if a_horizontal and b_horizontal and abs(a_start.y - b_start.y) < 0.05:
            left = max(min(a_start.x, a_end.x), min(b_start.x, b_end.x))
            right = min(max(a_start.x, a_end.x), max(b_start.x, b_end.x))
            if right - left > 0.05:
                y = (a_start.y + b_start.y) / 2.0
                return Point2D(left, y), Point2D(right, y)

        if a_vertical and b_vertical and abs(a_start.x - b_start.x) < 0.05:
            bottom = max(min(a_start.y, a_end.y), min(b_start.y, b_end.y))
            top = min(max(a_start.y, a_end.y), max(b_start.y, b_end.y))
            if top - bottom > 0.05:
                x = (a_start.x + b_start.x) / 2.0
                return Point2D(x, bottom), Point2D(x, top)

        return None

    def _get_wall_material(
        self, room_type_a: RoomType, room_type_b: RoomType, archetype: Optional[Archetype]
    ) -> str:
        if archetype is None:
            return "gypsum_double"

        for room_type in (room_type_a, room_type_b):
            if room_type.value in archetype.wall_overrides:
                return archetype.wall_overrides[room_type.value]

        if RoomType.CORRIDOR in (room_type_a, room_type_b):
            non_corridor = room_type_b if room_type_a == RoomType.CORRIDOR else room_type_a
            return archetype.wall_overrides.get(non_corridor.value, archetype.wall_interior_default)

        return archetype.wall_interior_default

    def _get_material_thickness(self, material_name: str) -> float:
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

    def _validate_building(self, building: Building) -> None:
        for floor in building.floors:
            if not floor.rooms:
                raise ValueError("Generated floor has no rooms")
            self._validate_floor_no_overlap(floor)

    def _validate_floor_no_overlap(self, floor: Floor) -> None:
        rects = [(room.id, self._rect_from_polygon(room.polygon)) for room in floor.rooms]
        for idx, (room_a, rect_a) in enumerate(rects):
            for room_b, rect_b in rects[idx + 1 :]:
                overlap_x = min(rect_a.max_x, rect_b.max_x) - max(rect_a.min_x, rect_b.min_x)
                overlap_y = min(rect_a.max_y, rect_b.max_y) - max(rect_a.min_y, rect_b.min_y)
                if overlap_x > 0.05 and overlap_y > 0.05:
                    raise ValueError(f"Rooms {room_a} and {room_b} overlap")

    def _rect_from_polygon(self, poly: Polygon2D) -> _Rect:
        bbox = poly.bounding_box()
        return _Rect(bbox.min_x, bbox.min_y, bbox.max_x, bbox.max_y)

    def _edge_on_bounds(self, start: Point2D, end: Point2D, bounds: _Rect) -> bool:
        return (
            abs(start.x - bounds.min_x) < EPS and abs(end.x - bounds.min_x) < EPS
            or abs(start.x - bounds.max_x) < EPS and abs(end.x - bounds.max_x) < EPS
            or abs(start.y - bounds.min_y) < EPS and abs(end.y - bounds.min_y) < EPS
            or abs(start.y - bounds.max_y) < EPS and abs(end.y - bounds.max_y) < EPS
        )

    def _edge_key(self, start: Point2D, end: Point2D) -> tuple[float, float, float, float]:
        if (start.x, start.y) <= (end.x, end.y):
            a, b = start, end
        else:
            a, b = end, start
        return (round(a.x, 4), round(a.y, 4), round(b.x, 4), round(b.y, 4))

    def _sorted_unique(self, values: list[float]) -> list[float]:
        result: list[float] = []
        for value in sorted(values):
            if not result or abs(result[-1] - value) > 1e-4:
                result.append(value)
        return result

    def _dedupe_preserve(self, values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result
