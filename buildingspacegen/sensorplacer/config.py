"""YAML-backed placement rule loading."""
from __future__ import annotations

import os

import yaml

from buildingspacegen.core.device import PlacementRules
from buildingspacegen.core.enums import BuildingType, RoomType

from .rules import DEFAULT_RULES, DEFAULT_WALL_MOUNT_OFFSET_M

_RULES_ENV_VAR = "BUILDINGSPACEGEN_PLACEMENT_RULES_PATH"


def _default_rules_path() -> str:
    return os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        "placement",
        "device_placement_rules.yaml",
    )


def load_placement_rules(
    building_type: BuildingType | str | None = None,
    path: str | None = None,
) -> PlacementRules:
    """Load placement rules from YAML, overlaying any building-type-specific settings."""
    rules_path = path or os.environ.get(_RULES_ENV_VAR) or _default_rules_path()
    if not os.path.exists(rules_path):
        return DEFAULT_RULES

    with open(rules_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    defaults = dict(data.get("defaults", {}))
    overlay = {}
    if building_type is not None:
        building_key = building_type.value if isinstance(building_type, BuildingType) else str(building_type)
        overlay = dict(data.get("by_building_type", {}).get(building_key, {}))

    merged = {**defaults, **overlay}
    if not merged:
        return DEFAULT_RULES

    excluded_room_types = [
        room_type if isinstance(room_type, RoomType) else RoomType(room_type)
        for room_type in merged.get("excluded_room_types", [])
    ]

    rules = PlacementRules(
        main_controller_per_sqft=float(merged.get("main_controller_per_sqft", DEFAULT_RULES.main_controller_per_sqft)),
        main_controller_wall_height_m=float(
            merged.get("main_controller_wall_height_m", DEFAULT_RULES.main_controller_wall_height_m)
        ),
        main_controller_prefer_center=bool(
            merged.get("main_controller_prefer_center", DEFAULT_RULES.main_controller_prefer_center)
        ),
        secondary_controller_per_sqft=float(
            merged.get("secondary_controller_per_sqft", DEFAULT_RULES.secondary_controller_per_sqft)
        ),
        secondary_controller_wall_height_m=float(
            merged.get("secondary_controller_wall_height_m", DEFAULT_RULES.secondary_controller_wall_height_m)
        ),
        sensor_min_per_room=int(merged.get("sensor_min_per_room", DEFAULT_RULES.sensor_min_per_room)),
        sensor_per_sqft=float(merged.get("sensor_per_sqft", DEFAULT_RULES.sensor_per_sqft)),
        sensor_wall_height_m=float(merged.get("sensor_wall_height_m", DEFAULT_RULES.sensor_wall_height_m)),
        sensor_min_spacing_m=float(merged.get("sensor_min_spacing_m", DEFAULT_RULES.sensor_min_spacing_m)),
        excluded_room_types=excluded_room_types or list(DEFAULT_RULES.excluded_room_types),
    )
    setattr(
        rules,
        "wall_mount_offset_m",
        float(merged.get("wall_mount_offset_m", DEFAULT_WALL_MOUNT_OFFSET_M)),
    )
    return rules
