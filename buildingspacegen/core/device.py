"""Device placement and radio profile models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .geometry import Point3D
from .enums import DeviceType, RoomType


@dataclass
class RadioProfile:
    """RF radio profile for a device."""
    name: str
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    rx_sensitivity_dbm: float
    supported_frequencies_hz: list[float]


@dataclass
class Device:
    """A placed device (controller or sensor)."""
    id: str
    device_type: DeviceType
    position: Point3D
    room_id: str
    wall_id: str  # Empty string if not wall-mounted
    radio_profile: RadioProfile
    metadata: dict = field(default_factory=dict)
    position_along_wall: Optional[float] = None
    mounted_side: Optional[str] = None
    offset_from_wall_m: float = 0.0


@dataclass
class PlacementRules:
    """Rules for placing devices."""
    main_controller_per_sqft: float
    main_controller_wall_height_m: float
    main_controller_prefer_center: bool
    secondary_controller_per_sqft: float
    secondary_controller_wall_height_m: float
    sensor_min_per_room: int
    sensor_per_sqft: float
    sensor_wall_height_m: float
    sensor_min_spacing_m: float
    excluded_room_types: list[RoomType] = field(default_factory=list)


@dataclass
class DevicePlacement:
    """Device placement result for a building."""
    building_seed: int
    devices: list[Device]
    placement_rules: PlacementRules

    def get_devices_by_type(self, dtype: DeviceType) -> list[Device]:
        """Get all devices of a given type."""
        return [d for d in self.devices if d.device_type == dtype]

    def get_devices_in_room(self, room_id: str) -> list[Device]:
        """Get all devices in a room."""
        return [d for d in self.devices if d.room_id == room_id]
