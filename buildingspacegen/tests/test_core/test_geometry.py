"""Tests for geometry primitives."""
import pytest
from buildingspacegen.core import Point2D, Point3D, LineSegment2D, Polygon2D, BBox


class TestPoint2D:
    def test_distance_to_same_point(self):
        p = Point2D(0, 0)
        assert p.distance_to(p) == 0.0

    def test_distance_to_other_point(self):
        p1 = Point2D(0, 0)
        p2 = Point2D(3, 4)
        assert abs(p1.distance_to(p2) - 5.0) < 0.001

    def test_to_3d(self):
        p2d = Point2D(1.0, 2.0)
        p3d = p2d.to_3d(3.0)
        assert p3d.x == 1.0
        assert p3d.y == 2.0
        assert p3d.z == 3.0


class TestPoint3D:
    def test_distance_to_same_point(self):
        p = Point3D(0, 0, 0)
        assert p.distance_to(p) == 0.0

    def test_distance_to_other_point(self):
        p1 = Point3D(0, 0, 0)
        p2 = Point3D(1, 2, 2)
        assert abs(p1.distance_to(p2) - 3.0) < 0.001

    def test_to_2d(self):
        p3d = Point3D(1.0, 2.0, 3.0)
        p2d = p3d.to_2d()
        assert p2d.x == 1.0
        assert p2d.y == 2.0


class TestLineSegment2D:
    def test_length(self):
        seg = LineSegment2D(Point2D(0, 0), Point2D(3, 4))
        assert abs(seg.length() - 5.0) < 0.001

    def test_point_at_fraction(self):
        seg = LineSegment2D(Point2D(0, 0), Point2D(10, 0))
        p = seg.point_at_fraction(0.5)
        assert p.x == 5.0
        assert p.y == 0.0

    def test_intersects_crossing(self):
        seg1 = LineSegment2D(Point2D(0, 1), Point2D(2, 1))
        seg2 = LineSegment2D(Point2D(1, 0), Point2D(1, 2))
        assert seg1.intersects(seg2)

    def test_intersects_parallel(self):
        seg1 = LineSegment2D(Point2D(0, 0), Point2D(2, 0))
        seg2 = LineSegment2D(Point2D(0, 1), Point2D(2, 1))
        assert not seg1.intersects(seg2)

    def test_intersection_point(self):
        seg1 = LineSegment2D(Point2D(0, 1), Point2D(2, 1))
        seg2 = LineSegment2D(Point2D(1, 0), Point2D(1, 2))
        pt = seg1.intersection_point(seg2)
        assert pt is not None
        assert abs(pt.x - 1.0) < 0.001
        assert abs(pt.y - 1.0) < 0.001


class TestBBox:
    def test_width_height_area(self):
        bbox = BBox(0, 0, 10, 5)
        assert bbox.width() == 10.0
        assert bbox.height() == 5.0
        assert bbox.area() == 50.0

    def test_center(self):
        bbox = BBox(0, 0, 10, 10)
        center = bbox.center()
        assert center.x == 5.0
        assert center.y == 5.0


class TestPolygon2D:
    def test_rectangle_area(self):
        poly = Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 5),
            Point2D(0, 5),
        ])
        assert abs(poly.area() - 50.0) < 0.1

    def test_centroid(self):
        poly = Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 5),
            Point2D(0, 5),
        ])
        centroid = poly.centroid()
        assert abs(centroid.x - 5.0) < 0.1
        assert abs(centroid.y - 2.5) < 0.1

    def test_contains_inside(self):
        poly = Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 10),
            Point2D(0, 10),
        ])
        assert poly.contains(Point2D(5, 5))

    def test_contains_outside(self):
        poly = Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 10),
            Point2D(0, 10),
        ])
        assert not poly.contains(Point2D(15, 5))

    def test_edges(self):
        poly = Polygon2D([
            Point2D(0, 0),
            Point2D(10, 0),
            Point2D(10, 10),
            Point2D(0, 10),
        ])
        edges = poly.edges()
        assert len(edges) == 4

    def test_bounding_box(self):
        poly = Polygon2D([
            Point2D(2, 3),
            Point2D(12, 3),
            Point2D(12, 13),
            Point2D(2, 13),
        ])
        bbox = poly.bounding_box()
        assert bbox.min_x == 2.0
        assert bbox.min_y == 3.0
        assert bbox.max_x == 12.0
        assert bbox.max_y == 13.0

    def test_invalid_polygon(self):
        with pytest.raises(ValueError):
            Polygon2D([Point2D(0, 0), Point2D(1, 1)])
