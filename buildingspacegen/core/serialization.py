"""JSON serialization for core models."""
from typing import Any, Optional
import json

from .model import (
    Building, Floor, Room, WallSegment, Door, Material
)
from .device import Device, DevicePlacement, RadioProfile, PlacementRules
from .links import PathLossGraph, LinkResult
from .geometry import Point2D, Polygon2D
from .enums import BuildingType, RoomType, WallMaterial, DeviceType


def _point2d_to_dict(p: Point2D) -> list[float]:
    """Serialize Point2D to [x, y]."""
    return [p.x, p.y]


def _polygon_to_dict(poly: Polygon2D) -> list[list[float]]:
    """Serialize Polygon2D to list of [x, y] pairs."""
    return [_point2d_to_dict(v) for v in poly.vertices]


def _material_to_dict(m: Material) -> dict[str, Any]:
    """Serialize Material."""
    return {
        "name": m.name,
        "thickness_m": m.thickness_m,
    }


def _material_from_dict(d: dict) -> Material:
    """Deserialize Material."""
    return Material(
        name=d["name"],
        thickness_m=d["thickness_m"],
    )


def _wall_segment_to_dict(w: WallSegment) -> dict[str, Any]:
    """Serialize WallSegment."""
    return {
        "id": w.id,
        "start": _point2d_to_dict(w.start),
        "end": _point2d_to_dict(w.end),
        "height": w.height,
        "materials": [_material_to_dict(m) for m in w.materials],
        "is_exterior": w.is_exterior,
        "room_ids": [w.room_ids[0], w.room_ids[1]],
    }


def _wall_segment_from_dict(d: dict) -> WallSegment:
    """Deserialize WallSegment."""
    return WallSegment(
        id=d["id"],
        start=Point2D(d["start"][0], d["start"][1]),
        end=Point2D(d["end"][0], d["end"][1]),
        height=d["height"],
        materials=[_material_from_dict(m) for m in d["materials"]],
        is_exterior=d["is_exterior"],
        room_ids=(d["room_ids"][0], d["room_ids"][1]),
    )


def _door_to_dict(door: Door) -> dict[str, Any]:
    """Serialize Door."""
    return {
        "id": door.id,
        "wall_id": door.wall_id,
        "position_along_wall": door.position_along_wall,
        "width": door.width,
        "height": door.height,
        "material": _material_to_dict(door.material),
    }


def _door_from_dict(d: dict) -> Door:
    """Deserialize Door."""
    return Door(
        id=d["id"],
        wall_id=d["wall_id"],
        position_along_wall=d["position_along_wall"],
        width=d["width"],
        height=d["height"],
        material=_material_from_dict(d["material"]),
    )


def _room_to_dict(room: Room) -> dict[str, Any]:
    """Serialize Room."""
    return {
        "id": room.id,
        "room_type": room.room_type.value,
        "polygon": _polygon_to_dict(room.polygon),
        "area_sqft": room.area_sqft,
        "area_sqm": room.area_sqm,
        "ceiling_height": room.ceiling_height,
        "wall_ids": room.wall_ids,
        "door_ids": room.door_ids,
        "metadata": room.metadata,
    }


def _room_from_dict(d: dict) -> Room:
    """Deserialize Room."""
    vertices = [Point2D(x, y) for x, y in d["polygon"]]
    polygon = Polygon2D(vertices)
    return Room(
        id=d["id"],
        room_type=RoomType(d["room_type"]),
        polygon=polygon,
        floor_index=d.get("floor_index", 0),
        wall_ids=d.get("wall_ids", []),
        door_ids=d.get("door_ids", []),
        ceiling_height=d["ceiling_height"],
        metadata=d.get("metadata", {}),
    )


def _floor_to_dict(floor: Floor) -> dict[str, Any]:
    """Serialize Floor."""
    return {
        "index": floor.index,
        "elevation": floor.elevation,
        "footprint": _polygon_to_dict(floor.footprint),
        "rooms": [_room_to_dict(r) for r in floor.rooms],
        "walls": [_wall_segment_to_dict(w) for w in floor.walls],
        "doors": [_door_to_dict(d) for d in floor.doors],
    }


def _floor_from_dict(d: dict) -> Floor:
    """Deserialize Floor."""
    footprint_verts = [Point2D(x, y) for x, y in d["footprint"]]
    footprint = Polygon2D(footprint_verts)
    rooms = [_room_from_dict(r) for r in d.get("rooms", [])]
    walls = [_wall_segment_from_dict(w) for w in d.get("walls", [])]
    doors = [_door_from_dict(do) for do in d.get("doors", [])]

    return Floor(
        index=d["index"],
        elevation=d["elevation"],
        footprint=footprint,
        rooms=rooms,
        walls=walls,
        doors=doors,
    )


def building_to_dict(building: Building) -> dict[str, Any]:
    """Serialize Building to dict."""
    return {
        "building_type": building.building_type.value,
        "total_area_sqft": building.total_area_sqft,
        "seed": building.seed,
        "footprint": _polygon_to_dict(building.footprint),
        "metadata": building.metadata,
        "floors": [_floor_to_dict(f) for f in building.floors],
    }


def building_from_dict(d: dict) -> Building:
    """Deserialize Building from dict."""
    footprint_verts = [Point2D(x, y) for x, y in d["footprint"]]
    footprint = Polygon2D(footprint_verts)
    floors = [_floor_from_dict(f) for f in d.get("floors", [])]

    return Building(
        building_type=BuildingType(d["building_type"]),
        total_area_sqft=d["total_area_sqft"],
        seed=d["seed"],
        footprint=footprint,
        metadata=d.get("metadata", {}),
        floors=floors,
    )


def _radio_profile_to_dict(rp: RadioProfile) -> dict[str, Any]:
    """Serialize RadioProfile."""
    return {
        "name": rp.name,
        "tx_power_dbm": rp.tx_power_dbm,
        "tx_antenna_gain_dbi": rp.tx_antenna_gain_dbi,
        "rx_antenna_gain_dbi": rp.rx_antenna_gain_dbi,
        "rx_sensitivity_dbm": rp.rx_sensitivity_dbm,
        "supported_frequencies_hz": rp.supported_frequencies_hz,
    }


def _radio_profile_from_dict(d: dict) -> RadioProfile:
    """Deserialize RadioProfile."""
    return RadioProfile(
        name=d["name"],
        tx_power_dbm=d["tx_power_dbm"],
        tx_antenna_gain_dbi=d["tx_antenna_gain_dbi"],
        rx_antenna_gain_dbi=d["rx_antenna_gain_dbi"],
        rx_sensitivity_dbm=d["rx_sensitivity_dbm"],
        supported_frequencies_hz=d["supported_frequencies_hz"],
    )


def _device_to_dict(device: Device) -> dict[str, Any]:
    """Serialize Device."""
    data = {
        "id": device.id,
        "device_type": device.device_type.value,
        "position": [device.position.x, device.position.y, device.position.z],
        "room_id": device.room_id,
        "wall_id": device.wall_id,
        "radio_profile_name": device.radio_profile.name,
        "metadata": device.metadata,
    }
    if device.position_along_wall is not None:
        data["position_along_wall"] = device.position_along_wall
    if device.mounted_side is not None:
        data["mounted_side"] = device.mounted_side
    if device.offset_from_wall_m != 0.0:
        data["offset_from_wall_m"] = device.offset_from_wall_m
    return data


def _device_from_dict(d: dict, radio_profiles_map: dict[str, RadioProfile]) -> Device:
    """Deserialize Device."""
    pos = d["position"]
    from .geometry import Point3D
    return Device(
        id=d["id"],
        device_type=DeviceType(d["device_type"]),
        position=Point3D(pos[0], pos[1], pos[2]),
        room_id=d["room_id"],
        wall_id=d.get("wall_id", ""),
        radio_profile=radio_profiles_map[d["radio_profile_name"]],
        metadata=d.get("metadata", {}),
        position_along_wall=d.get("position_along_wall"),
        mounted_side=d.get("mounted_side"),
        offset_from_wall_m=d.get("offset_from_wall_m", 0.0),
    )


def _link_result_to_dict(link: LinkResult) -> dict[str, Any]:
    """Serialize LinkResult."""
    return {
        "tx_device_id": link.tx_device_id,
        "rx_device_id": link.rx_device_id,
        "frequency_hz": link.frequency_hz,
        "distance_m": link.distance_m,
        "fspl_db": link.fspl_db,
        "wall_loss_db": link.wall_loss_db,
        "path_loss_db": link.path_loss_db,
        "rx_power_dbm": link.rx_power_dbm,
        "walls_crossed": link.walls_crossed,
        "wall_details": link.wall_details,
        "link_viable": link.link_viable,
        "link_margin_db": link.link_margin_db,
    }


def _link_result_from_dict(d: dict) -> LinkResult:
    """Deserialize LinkResult."""
    return LinkResult(
        tx_device_id=d["tx_device_id"],
        rx_device_id=d["rx_device_id"],
        frequency_hz=d["frequency_hz"],
        distance_m=d["distance_m"],
        fspl_db=d["fspl_db"],
        wall_loss_db=d["wall_loss_db"],
        path_loss_db=d["path_loss_db"],
        rx_power_dbm=d["rx_power_dbm"],
        walls_crossed=d["walls_crossed"],
        wall_details=d.get("wall_details", []),
        link_viable=d.get("link_viable", False),
        link_margin_db=d.get("link_margin_db", 0.0),
    )


def serialize_building_scene(
    building: Building,
    devices: Optional[DevicePlacement] = None,
    links: Optional[PathLossGraph] = None,
    radio_profiles: Optional[dict[str, RadioProfile]] = None,
) -> dict[str, Any]:
    """Serialize complete building scene to P.3 JSON schema."""
    result: dict[str, Any] = {
        "building": building_to_dict(building),
        "devices": None,
        "radio_profiles": None,
        "links": None,
        "simulation": None,
    }

    if devices is not None:
        result["devices"] = [_device_to_dict(d) for d in devices.devices]

    if radio_profiles is not None:
        result["radio_profiles"] = {
            name: _radio_profile_to_dict(rp)
            for name, rp in radio_profiles.items()
        }

    if links is not None:
        result["links"] = [_link_result_to_dict(link) for link in links.all_links]

    return result


def deserialize_building_scene(d: dict) -> tuple[Building, Optional[DevicePlacement], Optional[PathLossGraph]]:
    """Deserialize building scene from P.3 JSON."""
    building = building_from_dict(d["building"])

    devices = None
    radio_profiles_map = {}
    if d.get("radio_profiles"):
        radio_profiles_map = {
            name: _radio_profile_from_dict(rp)
            for name, rp in d["radio_profiles"].items()
        }

    if d.get("devices"):
        device_list = [_device_from_dict(dev_dict, radio_profiles_map) for dev_dict in d["devices"]]
        devices = DevicePlacement(
            building_seed=building.seed,
            devices=device_list,
            placement_rules=PlacementRules(
                main_controller_per_sqft=0.0,
                main_controller_wall_height_m=2.5,
                main_controller_prefer_center=True,
                secondary_controller_per_sqft=0.0,
                secondary_controller_wall_height_m=2.0,
                sensor_min_per_room=1,
                sensor_per_sqft=0.0,
                sensor_wall_height_m=1.5,
                sensor_min_spacing_m=3.0,
            ),
        )

    links = None
    if d.get("links"):
        links = PathLossGraph()
        for link_dict in d["links"]:
            link = _link_result_from_dict(link_dict)
            links.add_link(link)

    return building, devices, links
