"""Geometry primitives for BuildingSpaceGenerator."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass(frozen=True)
class Point2D:
    """2D point in space."""
    x: float
    y: float

    def distance_to(self, other: Point2D) -> float:
        """Compute Euclidean distance to another point."""
        return float(np.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2))

    def to_3d(self, z: float = 0.0) -> Point3D:
        """Convert to 3D point."""
        return Point3D(self.x, self.y, z)


@dataclass(frozen=True)
class Point3D:
    """3D point in space."""
    x: float
    y: float
    z: float

    def to_2d(self) -> Point2D:
        """Convert to 2D point (drop z)."""
        return Point2D(self.x, self.y)

    def distance_to(self, other: Point3D) -> float:
        """Compute Euclidean distance to another point."""
        return float(np.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        ))


@dataclass(frozen=True)
class LineSegment2D:
    """2D line segment."""
    start: Point2D
    end: Point2D

    def length(self) -> float:
        """Compute length of segment."""
        return self.start.distance_to(self.end)

    def intersects(self, other: LineSegment2D) -> bool:
        """Check if this segment intersects with another."""
        return self._segments_intersect(
            (self.start.x, self.start.y), (self.end.x, self.end.y),
            (other.start.x, other.start.y), (other.end.x, other.end.y)
        )

    def intersection_point(self, other: LineSegment2D) -> Optional[Point2D]:
        """Get intersection point if segments intersect (not collinear)."""
        pt = self._line_intersection(
            (self.start.x, self.start.y), (self.end.x, self.end.y),
            (other.start.x, other.start.y), (other.end.x, other.end.y)
        )
        if pt is None:
            return None
        return Point2D(pt[0], pt[1])

    @staticmethod
    def _segments_intersect(p1: tuple, p2: tuple, p3: tuple, p4: tuple) -> bool:
        """Check if two line segments intersect."""
        def ccw(A, B, C):
            return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
        return ccw(p1,p3,p4) != ccw(p2,p3,p4) and ccw(p1,p2,p3) != ccw(p1,p2,p4)

    @staticmethod
    def _line_intersection(p1: tuple, p2: tuple, p3: tuple, p4: tuple) -> Optional[tuple]:
        """Get intersection point of two line segments, if it exists."""
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4

        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None  # Parallel

        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        u = -((x1-x2)*(y1-y3) - (y1-y2)*(x1-x3)) / denom

        if 0 <= t <= 1 and 0 <= u <= 1:
            x = x1 + t*(x2-x1)
            y = y1 + t*(y2-y1)
            return (x, y)
        return None

    def point_at_fraction(self, t: float) -> Point2D:
        """Get point at parameter t (0=start, 1=end) along segment."""
        x = self.start.x + t * (self.end.x - self.start.x)
        y = self.start.y + t * (self.end.y - self.start.y)
        return Point2D(x, y)


@dataclass(frozen=True)
class BBox:
    """Bounding box."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def width(self) -> float:
        """Width of bounding box."""
        return self.max_x - self.min_x

    def height(self) -> float:
        """Height of bounding box."""
        return self.max_y - self.min_y

    def area(self) -> float:
        """Area of bounding box."""
        return self.width() * self.height()

    def center(self) -> Point2D:
        """Center point of bounding box."""
        return Point2D(
            (self.min_x + self.max_x) / 2.0,
            (self.min_y + self.max_y) / 2.0
        )


@dataclass
class Polygon2D:
    """2D polygon with counter-clockwise winding."""
    vertices: list[Point2D]

    def __post_init__(self):
        """Validate polygon."""
        if len(self.vertices) < 3:
            raise ValueError("Polygon must have at least 3 vertices")

    def area(self) -> float:
        """Compute polygon area using shoelace formula."""
        verts = self.vertices
        n = len(verts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += verts[i].x * verts[j].y
            area -= verts[j].x * verts[i].y
        return abs(area) / 2.0

    def centroid(self) -> Point2D:
        """Compute polygon centroid."""
        verts = self.vertices
        n = len(verts)
        cx, cy = 0.0, 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            cross = verts[i].x * verts[j].y - verts[j].x * verts[i].y
            area += cross
            cx += (verts[i].x + verts[j].x) * cross
            cy += (verts[i].y + verts[j].y) * cross
        if abs(area) < 1e-10:
            # Degenerate polygon, return average
            cx = sum(v.x for v in verts) / n
            cy = sum(v.y for v in verts) / n
            return Point2D(cx, cy)
        return Point2D(cx / (3.0 * area), cy / (3.0 * area))

    def contains(self, point: Point2D) -> bool:
        """Check if point is inside polygon using ray casting."""
        x, y = point.x, point.y
        n = len(self.vertices)
        inside = False
        p1x, p1y = self.vertices[0].x, self.vertices[0].y
        for i in range(1, n + 1):
            p2x, p2y = self.vertices[i % n].x, self.vertices[i % n].y
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def edges(self) -> list[LineSegment2D]:
        """Get list of edges."""
        edges = []
        for i in range(len(self.vertices)):
            v1 = self.vertices[i]
            v2 = self.vertices[(i + 1) % len(self.vertices)]
            edges.append(LineSegment2D(v1, v2))
        return edges

    def bounding_box(self) -> BBox:
        """Get bounding box."""
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        return BBox(min(xs), min(ys), max(xs), max(ys))
